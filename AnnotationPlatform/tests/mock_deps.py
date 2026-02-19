"""
Mock external dependencies so that application code can be imported
without installing pydantic, fastapi, sqlalchemy, etc.

This module must be imported BEFORE any application code.
It injects mock modules into sys.modules for all external dependencies.
"""

import sys
import types
import uuid
import enum
from unittest.mock import MagicMock, PropertyMock
from datetime import datetime


def create_mock_module(name, attrs=None):
    """Create a mock module and register it in sys.modules."""
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ── Pydantic ─────────────────────────────────────────────────

class _BaseModel:
    """Minimal pydantic BaseModel mock."""
    model_config = {}

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.__dict__.update(kwargs)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Parse annotations for Field defaults
        annotations = {}
        for klass in reversed(cls.__mro__):
            if hasattr(klass, '__annotations__'):
                annotations.update(klass.__annotations__)
        cls.__annotations__ = annotations

    def model_dump(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            return cls(**obj)
        data = {}
        for key in getattr(cls, '__annotations__', {}):
            if hasattr(obj, key):
                data[key] = getattr(obj, key)
        return cls(**data)


class _Field:
    def __init__(self, **kwargs):
        self.default = kwargs.get('default', None)
        self.default_factory = kwargs.get('default_factory', None)

    def __call__(self, **kwargs):
        return _Field(**kwargs)


def _field_func(**kwargs):
    return kwargs.get('default', None)


class _EmailStr(str):
    pass


# Pydantic modules
pydantic = create_mock_module('pydantic', {
    'BaseModel': _BaseModel,
    'Field': _field_func,
    'EmailStr': _EmailStr,
    'HttpUrl': str,
    'field_validator': lambda *a, **kw: lambda f: f,
    'model_validator': lambda *a, **kw: lambda f: f,
})

pydantic_settings = create_mock_module('pydantic_settings', {
    'BaseSettings': _BaseModel,
})


# ── SQLAlchemy ───────────────────────────────────────────────

class _DeclarativeBase:
    metadata = MagicMock()

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


class _Mapped:
    def __class_getitem__(cls, item):
        return item


class _ColumnMock(MagicMock):
    """Mock for SQLAlchemy mapped columns with query operators."""
    pass


def _mapped_column(*args, **kwargs):
    return _ColumnMock()


def _relationship(*args, **kwargs):
    return []


def _select(*args, **kwargs):
    m = MagicMock()
    m.where = MagicMock(return_value=m)
    m.join = MagicMock(return_value=m)
    m.group_by = MagicMock(return_value=m)
    m.limit = MagicMock(return_value=m)
    m.order_by = MagicMock(return_value=m)
    return m


def _update(*args, **kwargs):
    m = MagicMock()
    m.where = MagicMock(return_value=m)
    m.values = MagicMock(return_value=m)
    return m


# Column types
for mod_name in [
    'sqlalchemy', 'sqlalchemy.orm', 'sqlalchemy.ext', 'sqlalchemy.ext.asyncio',
    'sqlalchemy.dialects', 'sqlalchemy.dialects.postgresql',
]:
    if mod_name not in sys.modules:
        create_mock_module(mod_name)

sa = sys.modules['sqlalchemy']
sa.Boolean = MagicMock()
sa.DateTime = MagicMock()
sa.Enum = lambda *a, **kw: MagicMock()
sa.Float = MagicMock()
sa.ForeignKey = lambda *a, **kw: MagicMock()
sa.Index = MagicMock()
sa.Integer = MagicMock()
sa.BigInteger = MagicMock()
sa.String = lambda *a, **kw: MagicMock()
sa.Text = MagicMock()
sa.UniqueConstraint = MagicMock()
sa.func = MagicMock()
sa.select = _select
sa.update = _update
sa.Column = MagicMock()
sa.create_engine = MagicMock()

sa_orm = sys.modules['sqlalchemy.orm']
sa_orm.DeclarativeBase = _DeclarativeBase
sa_orm.Mapped = _Mapped
sa_orm.mapped_column = _mapped_column
sa_orm.relationship = _relationship
sa_orm.Session = MagicMock

sa_async = sys.modules['sqlalchemy.ext.asyncio']
sa_async.AsyncSession = MagicMock
sa_async.async_sessionmaker = MagicMock(return_value=MagicMock())
sa_async.create_async_engine = MagicMock(return_value=MagicMock())

sa_pg = sys.modules['sqlalchemy.dialects.postgresql']
sa_pg.UUID = lambda *a, **kw: MagicMock()
sa_pg.JSONB = MagicMock()
sa_pg.ARRAY = MagicMock()


# ── FastAPI ──────────────────────────────────────────────────

class _HTTPException(Exception):
    def __init__(self, status_code=500, detail="", headers=None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


class _status:
    HTTP_200_OK = 200
    HTTP_201_CREATED = 201
    HTTP_204_NO_CONTENT = 204
    HTTP_400_BAD_REQUEST = 400
    HTTP_401_UNAUTHORIZED = 401
    HTTP_403_FORBIDDEN = 403
    HTTP_404_NOT_FOUND = 404
    HTTP_409_CONFLICT = 409
    HTTP_422_UNPROCESSABLE_ENTITY = 422


class _Depends:
    def __init__(self, fn=None):
        self.fn = fn

    def __call__(self, fn=None):
        return _Depends(fn)


class _APIRouter:
    def __init__(self, **kwargs):
        self.routes = []

    def get(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def post(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def put(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def patch(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def delete(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def include_router(self, *args, **kwargs):
        pass


class _FastAPI(_APIRouter):
    def add_middleware(self, *args, **kwargs):
        pass


def _Header(*args, **kwargs):
    return kwargs.get('default', None)


class _HTTPBearer:
    def __init__(self, **kwargs):
        pass


class _HTTPAuthorizationCredentials:
    def __init__(self, scheme="Bearer", credentials=""):
        self.scheme = scheme
        self.credentials = credentials


class _WebSocket:
    """Mock WebSocket for testing."""
    def __init__(self, **kwargs):
        self._accepted = False
        self._sent = []

    async def accept(self):
        self._accepted = True

    async def send_json(self, data):
        self._sent.append(data)

    async def receive_json(self):
        return {"type": "ping"}

    async def close(self, code=1000, reason=""):
        pass


class _WebSocketDisconnect(Exception):
    def __init__(self, code=1000):
        self.code = code


class _BaseHTTPMiddleware:
    def __init__(self, app=None, **kwargs):
        self.app = app


for mod_name in [
    'fastapi', 'fastapi.middleware', 'fastapi.middleware.cors',
    'fastapi.security', 'fastapi.responses',
    'fastapi.exceptions',
    'starlette', 'starlette.middleware', 'starlette.middleware.base',
]:
    if mod_name not in sys.modules:
        create_mock_module(mod_name)

fa = sys.modules['fastapi']
fa.FastAPI = _FastAPI
fa.APIRouter = _APIRouter
fa.Depends = _Depends()
fa.HTTPException = _HTTPException
fa.Header = _Header
fa.status = _status
fa.Request = MagicMock
fa.Response = MagicMock
fa.UploadFile = MagicMock
fa.File = MagicMock
fa.Query = lambda *a, **kw: kw.get('default', None)
fa.Path = lambda *a, **kw: kw.get('default', None)
fa.Body = lambda *a, **kw: kw.get('default', None)
fa.Form = lambda *a, **kw: kw.get('default', None)
fa.WebSocket = _WebSocket
fa.WebSocketDisconnect = _WebSocketDisconnect

fa_cors = sys.modules['fastapi.middleware.cors']
fa_cors.CORSMiddleware = MagicMock

fa_sec = sys.modules['fastapi.security']
fa_sec.HTTPBearer = _HTTPBearer
fa_sec.HTTPAuthorizationCredentials = _HTTPAuthorizationCredentials

fa_resp = sys.modules['fastapi.responses']
fa_resp.ORJSONResponse = MagicMock
fa_resp.JSONResponse = MagicMock

fa_exc = sys.modules['fastapi.exceptions']
fa_exc.RequestValidationError = type('RequestValidationError', (Exception,), {
    'errors': lambda self: [],
    '__init__': lambda self, errors=None, **kw: (super(type(self), self).__init__(), setattr(self, '_errors', errors or []))[0],
})

# Starlette
starlette_mid = sys.modules['starlette.middleware.base']
starlette_mid.BaseHTTPMiddleware = _BaseHTTPMiddleware


# ── Other dependencies ───────────────────────────────────────

# structlog
_structlog_mock = create_mock_module('structlog', {
    'get_logger': lambda: MagicMock(),
    'configure': lambda **kw: None,
    'make_filtering_bound_logger': lambda level: MagicMock,
    'PrintLoggerFactory': MagicMock,
    'processors': MagicMock(),
    'contextvars': MagicMock(),
    'dev': MagicMock(),
})

# jose (JWT)
class _JWTError(Exception):
    pass


_jose_jwt_mock = MagicMock()

create_mock_module('jose', {
    'JWTError': _JWTError,
    'jwt': _jose_jwt_mock,
})

# passlib
_pwd_context_mock = MagicMock()
create_mock_module('passlib', {})
create_mock_module('passlib.context', {
    'CryptContext': lambda **kw: _pwd_context_mock,
})

# minio
class _S3Error(Exception):
    pass

create_mock_module('minio', {
    'Minio': MagicMock,
})
create_mock_module('minio.error', {
    'S3Error': _S3Error,
})

# qdrant_client
create_mock_module('qdrant_client', {
    'QdrantClient': MagicMock,
    'models': MagicMock(),
})
create_mock_module('qdrant_client.http', {})
create_mock_module('qdrant_client.http.exceptions', {
    'UnexpectedResponse': type('UnexpectedResponse', (Exception,), {}),
})

# tenacity
def _retry(**kwargs):
    def decorator(fn):
        return fn
    return decorator

create_mock_module('tenacity', {
    'retry': _retry,
    'stop_after_attempt': lambda n: n,
    'wait_exponential': lambda **kw: None,
})

# celery
class _SharedTask:
    """Mock Celery task decorator."""
    def __init__(self, fn=None, **kwargs):
        self.fn = fn
        self.name = kwargs.get('name', '')

    def __call__(self, *args, **kwargs):
        if self.fn is None and args and callable(args[0]):
            self.fn = args[0]
            return self
        return self.fn(*args, **kwargs)

    def delay(self, *args, **kwargs):
        return MagicMock()

    def s(self, *args, **kwargs):
        m = MagicMock()
        m.set = MagicMock(return_value=m)
        return m

    def apply_async(self, *args, **kwargs):
        return MagicMock()


def _shared_task(*args, **kwargs):
    if args and callable(args[0]):
        return _SharedTask(args[0])
    return _SharedTask(**kwargs)


def _celery_group(tasks):
    """Mock celery group that returns an object with apply_async."""
    m = MagicMock()
    m.apply_async.return_value = MagicMock(id=str(uuid.uuid4()))
    return m

create_mock_module('celery', {
    'Celery': MagicMock,
    'shared_task': _shared_task,
    'group': _celery_group,
})
create_mock_module('celery.signals', {
    'worker_init': MagicMock(),
})

# torch, numpy, PIL, etc.
create_mock_module('torch', {
    'no_grad': MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())),
    'cuda': MagicMock(),
    'amp': MagicMock(),
    'stack': MagicMock(),
    'float16': 'float16',
    'float32': 'float32',
})
sys.modules['torch'].cuda.is_available = MagicMock(return_value=False)

create_mock_module('numpy', {
    'ndarray': MagicMock,
})
create_mock_module('PIL', {})
create_mock_module('PIL.Image', {
    'Image': MagicMock,
    'open': MagicMock(),
})
create_mock_module('torchvision', {})
create_mock_module('torchvision.transforms', {
    'Compose': MagicMock,
    'Resize': MagicMock,
    'CenterCrop': MagicMock,
    'ToTensor': MagicMock,
    'Normalize': MagicMock,
    'InterpolationMode': MagicMock(),
})

# open_clip, sentence_transformers, transformers
create_mock_module('open_clip', {
    'create_model_and_transforms': MagicMock(return_value=(MagicMock(), None, MagicMock())),
    'get_tokenizer': MagicMock(return_value=MagicMock()),
})
create_mock_module('sentence_transformers', {
    'SentenceTransformer': MagicMock,
})
create_mock_module('transformers', {
    'AutoProcessor': MagicMock(),
    'Blip2ForConditionalGeneration': MagicMock(),
})

# redis
create_mock_module('redis', {
    'from_url': MagicMock,
})

# orjson
create_mock_module('orjson', {
    'dumps': lambda x, **kw: __import__('json').dumps(x).encode(),
    'loads': lambda x: __import__('json').loads(x),
    'OPT_NON_STR_KEYS': 0,
})

# bcrypt (passlib dependency)
create_mock_module('bcrypt', {
    '__version__': '4.0.0',
})

# asyncpg
create_mock_module('asyncpg', {})


# ── Expose references for test assertions ────────────────────

def get_jose_jwt_mock():
    return _jose_jwt_mock


def get_pwd_context_mock():
    return _pwd_context_mock


def get_s3_error_class():
    return _S3Error


def get_http_exception_class():
    return _HTTPException


def get_websocket_class():
    return _WebSocket


def get_websocket_disconnect_class():
    return _WebSocketDisconnect
