import logging
import os
from autouri import AutoURI, AbsPath, GCSURI, S3URI
from datetime import datetime
from .server_heartbeat import ServerHeartbeat


logger = logging.getLogger(__name__)


class CaperBase:
    DEFAULT_SERVER_HEARTBEAT_FILE = '~/.caper/default_server_heartbeat'

    def __init__(
            self,
            tmp_dir,
            tmp_gcs_bucket=None,
            tmp_s3_bucket=None,
            server_heartbeat_file=DEFAULT_SERVER_HEARTBEAT_FILE,
            server_heartbeat_timeout=ServerHeartbeat.DEFAULT_HEARTBEAT_TIMEOUT_MS):
        """1) Manages cache/temp directories for localization on the following
        storages:
            - Local*: Local path -> tmp_dir**
            - gcp: GCS bucket path -> tmp_gcs_bucket
            - aws: S3 bucket path -> tmp_s3_bucket
            * Note that it starts with capital L.
            ** /tmp is not allowed here. This directory is very important to store
            intermediate files used by Cromwell/AutoURI (filter transfer/localization).

        2) Also manages a server heartbeat file that includes
        hostname/port of a running Cromwell server.
        Server can write this file to pass hostname/port to clients.

        Args:
            tmp_dir:
                Local cache directory to store files files localized for Local backend.
            tmp_gcs_bucket:
                GCS cache directory to store files localized on GCS for gcp backend.
            tmp_s3_bucket:
                S3 cache directory to store files localized on S3 for aws backend.
            server_heartbeat_file:
                Server heartbeat file to write/read hostname/port.
            server_heartbeat_timeout:
                Timeout for heartbeat file.
                Only fresh heartbeat file within this time limit is used.
        """
        if not AbsPath(tmp_dir).is_valid:
            raise ValueError(
                'tmp_dir should be a valid local abspath. {f}'.format(f=tmp_dir))
        if tmp_dir == '/tmp':
            raise ValueError(
                '/tmp is now allowed for tmp_dir. {f}'.format(f=tmp_dir))
        if tmp_gcs_bucket and not GCSURI(tmp_gcs_bucket).is_valid:
            raise ValueError(
                'tmp_gcs_bucket should be a valid GCS path. {f}'.format(f=tmp_gcs_bucket))
        if tmp_s3_bucket and not S3URI(tmp_s3_bucket).is_valid:
            raise ValueError(
                'tmp_s3_bucket should be a valid S3 path. {f}'.format(f=tmp_s3_bucket))

        self._tmp_dir = tmp_dir
        self._tmp_gcs_bucket = tmp_gcs_bucket
        self._tmp_s3_bucket = tmp_s3_bucket

        if server_heartbeat_file:
            self._server_heartbeat = ServerHeartbeat(
                heartbeat_file=server_heartbeat_file,
                heartbeat_timeout=server_heartbeat_timeout)
        else:
            self._server_heartbeat = None

    @property
    def server_heartbeat(self):
        return self._server_heartbeat

    def localize_on_backend(self, f, backend, recursive=False, make_md5_file=False):
        """Localize a file according to the chosen backend.
        Each backend has its corresponding storage.
            - gcp -> GCS bucket path (starting with gs://)
            - aws -> S3 bucket path (starting with s3://)
            - All others (based on local backend) -> local storage

        If contents of input JSON changes due to recursive localization (deepcopy)
        then a new temporary file suffixed with backend type will be written on loc_prefix.
        For example, /somewhere/test.json -> gs://example-tmp-gcs-bucket/somewhere/test.gcs.json

        loc_prefix will be one of the cache directories according to the backend type
            - gcp -> tmp_gcs_bucket
            - aws -> tmp_s3_bucket
            - all others (local) -> tmp_dir

        Args:
            f:
                File to be localized.
            backend:
                Backend to localize file f on.
            recursive:
                Recursive localization (deepcopy).
                All files (if value is valid path/URI string) in JSON/CSV/TSV
                will be localized together with file f.
            make_md5_file:
                Make .md5 file for localized files. This is for local only since
                GCS/S3 bucket paths already include md5 hash information in their metadata.
        """
        if backend == BACKEND_GCP:
            loc_prefix = self._tmp_gcs_bucket
        elif backend == BACKEND_AWS:
            loc_prefix = self._tmp_s3_bucket
        else:
            loc_prefix = self._tmp_dir

        return AutoURI(f).localize_on(
            loc_prefix, recursive=recursive, make_md5_file=make_md5_file)

    def create_timestamped_tmp_dir(self, prefix=''):
        """Creates/returns a local temporary directory on self._tmp_dir.        

        Args:
            prefix:
                Prefix for timstamped directory.
                Directory name will be self._tmpdir / prefix / timestamp.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        tmp_dir = os.path.join(self._tmp_dir, prefix, timestamp)
        os.makedirs(tmp_dir, exist_ok=True)
        logger.info(
            'Creating a timestamped temporary directory. {d}'.format(
                d=tmp_dir))

        return tmp_dir
