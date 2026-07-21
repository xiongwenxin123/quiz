"""Small compatibility surface for Pydantic 1 on the Android runtime."""

from __future__ import annotations

import re
from typing import Any, Callable

from pydantic import HttpUrl, ValidationError

try:
    from pydantic import BaseModel, Field, model_validator

    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import Field
    from pydantic import root_validator

    PYDANTIC_V2 = False

    class BaseModel(_PydanticBaseModel):
        """Expose the Pydantic 2 methods used by the application."""

        @classmethod
        def model_validate(cls, value: Any) -> BaseModel:
            return cls.parse_obj(value)

        @classmethod
        def model_validate_json(cls, value: str | bytes) -> BaseModel:
            return cls.parse_raw(value)

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            return cls.schema()

        def model_dump(self, **kwargs: Any) -> dict[str, Any]:
            return self.dict(**kwargs)

        def model_dump_json(self, **kwargs: Any) -> str:
            return self.json(**kwargs)

        def model_copy(self, **kwargs: Any) -> BaseModel:
            return self.copy(**kwargs)

        @root_validator(allow_reuse=True, skip_on_failure=True)
        def _enforce_v2_collection_constraints(
            cls, values: dict[str, Any]
        ) -> dict[str, Any]:
            # Pydantic 1 stores v2's list length and pattern arguments but does
            # not enforce them, so retain the same API contract here.
            for name, value in values.items():
                field = cls.__fields__.get(name)
                if field is None:
                    continue
                info = field.field_info
                if isinstance(value, list):
                    if info.min_length is not None and len(value) < info.min_length:
                        raise ValueError(
                            f"{name} must contain at least {info.min_length} items"
                        )
                    if info.max_length is not None and len(value) > info.max_length:
                        raise ValueError(
                            f"{name} must contain at most {info.max_length} items"
                        )
                pattern = info.extra.get("pattern")
                if pattern and isinstance(value, str) and re.search(pattern, value) is None:
                    raise ValueError(f"{name} does not match the required pattern")
            return values

    def model_validator(*, mode: str) -> Callable[[Callable[..., Any]], classmethod]:
        def decorate(function: Callable[..., Any]) -> classmethod:
            target = function.__func__ if isinstance(function, classmethod) else function

            if mode == "before":
                def validate_before(
                    cls: type[BaseModel], values: dict[str, Any]
                ) -> dict[str, Any]:
                    return target(cls, values)

                validate_before.__name__ = target.__name__
                return root_validator(pre=True, allow_reuse=True)(validate_before)
            if mode != "after":
                raise NotImplementedError(f"Unsupported model validator mode: {mode}")

            def validate(cls: type[BaseModel], values: dict[str, Any]) -> dict[str, Any]:
                instance = cls.construct(_fields_set=set(values), **values)
                result = target(instance)
                if isinstance(result, dict):
                    return result
                return values

            validate.__name__ = target.__name__
            return root_validator(allow_reuse=True, skip_on_failure=True)(validate)

        return decorate


def ListField(*args: Any, **kwargs: Any) -> Any:
    """Create a list field with equivalent length constraints on both versions."""
    if not PYDANTIC_V2:
        if "min_length" in kwargs:
            kwargs["min_items"] = kwargs.pop("min_length")
        if "max_length" in kwargs:
            kwargs["max_items"] = kwargs.pop("max_length")
    return Field(*args, **kwargs)


__all__ = [
    "BaseModel",
    "Field",
    "HttpUrl",
    "ListField",
    "PYDANTIC_V2",
    "ValidationError",
    "model_validator",
]
