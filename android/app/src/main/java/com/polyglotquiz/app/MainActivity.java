package com.polyglotquiz.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.Toast;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String APP_URL = "http://127.0.0.1:8765/";
    private final ExecutorService executor = Executors.newFixedThreadPool(2);
    private WebView webView;
    private ProgressBar progressBar;

    @Override
    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        progressBar = findViewById(R.id.startup_progress);
        webView = findViewById(R.id.web_view);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.setBackgroundColor(Color.rgb(247, 248, 246));
        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");
        webView.setWebViewClient(new LocalWebViewClient());

        executor.execute(this::startPythonServer);
        executor.execute(this::waitForServer);
    }

    private void startPythonServer() {
        try {
            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(getApplicationContext()));
            }
            Python python = Python.getInstance();
            python.getModule("polyglot_quiz.mobile")
                    .callAttr("configure", getFilesDir().getAbsolutePath());
            python.getModule("polyglot_quiz.mobile").callAttr("run_server");
        } catch (Throwable error) {
            runOnUiThread(() -> showStartupError(error));
        }
    }

    private void waitForServer() {
        for (int attempt = 0; attempt < 100; attempt++) {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(APP_URL + "health").openConnection();
                connection.setConnectTimeout(300);
                connection.setReadTimeout(300);
                if (connection.getResponseCode() == 200) {
                    runOnUiThread(() -> {
                        progressBar.setVisibility(View.GONE);
                        webView.setVisibility(View.VISIBLE);
                        webView.loadUrl(APP_URL);
                    });
                    return;
                }
            } catch (IOException ignored) {
                // The embedded interpreter is still importing dependencies.
            } finally {
                if (connection != null) connection.disconnect();
            }
            try {
                Thread.sleep(100L);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return;
            }
        }
        runOnUiThread(() -> showStartupError(new IllegalStateException("服务启动超时")));
    }

    private void showStartupError(Throwable error) {
        progressBar.setVisibility(View.GONE);
        Toast.makeText(this, "应用服务启动失败：" + error.getMessage(), Toast.LENGTH_LONG).show();
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        webView.destroy();
        executor.shutdownNow();
        super.onDestroy();
    }

    private final class LocalWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            if ("127.0.0.1".equals(uri.getHost())) return false;
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
            return true;
        }
    }

    private final class AndroidBridge {
        @JavascriptInterface
        public void saveJson(String json, String filename) {
            executor.execute(() -> {
                try {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        ContentValues values = new ContentValues();
                        values.put(MediaStore.Downloads.DISPLAY_NAME, filename);
                        values.put(MediaStore.Downloads.MIME_TYPE, "application/json");
                        values.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                        Uri uri = getContentResolver().insert(
                                MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                        if (uri == null) throw new IOException("无法创建下载文件");
                        try (OutputStream output = getContentResolver().openOutputStream(uri)) {
                            if (output == null) throw new IOException("无法打开下载文件");
                            output.write(json.getBytes(StandardCharsets.UTF_8));
                        }
                    } else {
                        File directory = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                        if (directory == null) throw new IOException("下载目录不可用");
                        try (OutputStream output = new FileOutputStream(new File(directory, filename))) {
                            output.write(json.getBytes(StandardCharsets.UTF_8));
                        }
                    }
                } catch (IOException error) {
                    runOnUiThread(() -> Toast.makeText(
                            MainActivity.this,
                            "JSON 导出失败：" + error.getMessage(),
                            Toast.LENGTH_LONG).show());
                }
            });
        }
    }
}
