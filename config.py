import tempfile
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    '''Deployment settings, loaded and validated once at startup.

    Field names are UPPER_CASE and match the environment variable names they
    are read from. Reads are case-sensitive to mirror the previous
    ``os.environ`` access.
    '''
    model_config = SettingsConfigDict(case_sensitive=True)

    DEBUG: bool = False
    TESTING: bool = False

    MONGO_HOST: str = 'mongomock://localhost'

    MINIO_HOST: Optional[str] = None
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None
    MINIO_BUCKET: str = 'normal-oj-testing'
    MINIO_REGION: Optional[str] = None

    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[int] = None

    # JWT_EXP is kept as an int (days); the timedelta is built at the use site.
    # Typing it as timedelta would make pydantic parse env ints as seconds.
    JWT_EXP: int = 30
    JWT_ISS: str = 'test.test'
    JWT_SECRET: str = 'SuperSecretString'

    SMTP_SERVER: Optional[str] = None
    SMTP_NOREPLY: Optional[str] = None
    SMTP_NOREPLY_PASSWORD: Optional[str] = None

    SUBMISSION_TMP_DIR: str = None  # type: ignore[assignment]

    @field_validator('SUBMISSION_TMP_DIR', mode='before')
    @classmethod
    def _default_submission_tmp_dir(cls, v):
        # Keep a real, persistent directory. The previous
        # ``tempfile.TemporaryDirectory(...).name`` kept no object reference, so
        # the directory was deleted on GC. Also fixes the 'noj-submisisons' typo.
        if v is None:
            return tempfile.mkdtemp(suffix='noj-submissions')
        return v

    @field_validator('TESTING', mode='before')
    @classmethod
    def _lenient_testing(cls, v):
        '''Interpret ``1``, ``true``, and ``yes`` (case-insensitive) as True.

        Any other value — including the common mistake of setting
        ``TESTING=false`` — is treated as False.
        '''
        if isinstance(v, str):
            return v.lower() in ('1', 'true', 'yes')
        return v

    @model_validator(mode='after')
    def _require_smtp_noreply(self):
        if self.SMTP_SERVER is not None and self.SMTP_NOREPLY is None:
            raise ValueError("missing required configuration 'SMTP_NOREPLY'")
        return self


settings = Settings()
