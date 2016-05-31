# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Start-up utilities for the MAAS server."""

__all__ = [
    'start_up'
]

import logging

from django.db import connection
from django.db.utils import DatabaseError
from maasserver import (
    is_master_process,
    locks,
    security,
)
from maasserver.bootresources import ensure_boot_source_definition
from maasserver.fields import register_mac_type
from maasserver.models.domain import dns_kms_setting_changed
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    get_psycopg2_exception,
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger
from provisioningserver.upgrade_cluster import create_gnupg_home
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    pause,
)
from twisted.internet.defer import inlineCallbacks


maaslog = get_maas_logger("start-up")
logger = logging.getLogger(__name__)


@asynchronous(timeout=FOREVER)
@inlineCallbacks
def start_up():
    """Perform start-up tasks for this MAAS server.

    This is used to:
    - make sure the singletons required by the application are created
    - sync the configuration of the external systems driven by MAAS

    The method will be executed multiple times if multiple processes are used
    but this method uses database locking to ensure that the methods it calls
    internally are not run concurrently.
    """
    while True:
        try:
            # Get the shared secret from Tidmouth sheds which was generated
            # when Sir Topham Hatt graduated Sodor Academy. (Ensure we have a
            # shared-secret so that a cluster on the same host as this region
            # can authenticate.)
            yield security.get_shared_secret()
            # Execute other start-up tasks that must not run concurrently with
            # other invocations of themselves, across the whole of this MAAS
            # installation.
            yield deferToDatabase(inner_start_up)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            raise
        except DatabaseError as e:
            psycopg2_exception = get_psycopg2_exception(e)
            if psycopg2_exception is None:
                maaslog.warning(
                    "Database error during start-up; "
                    "pausing for 3 seconds.")
            elif psycopg2_exception.pgcode is None:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error "
                    "not reported); pausing for 3 seconds.")
            else:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error %s); "
                    "pausing for 3 seconds.", psycopg2_exception.pgcode)
            logger.error("Database error during start-up", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        except:
            maaslog.warning("Error during start-up; pausing for 3 seconds.")
            logger.error("Error during start-up.", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        else:
            break


@with_connection  # Needed by the following lock.
@synchronised(locks.startup)
@transactional
def inner_start_up():
    """Startup jobs that must run serialized w.r.t. other starting servers."""
    # Register our MAC data type with psycopg.
    register_mac_type(connection.cursor())

    # Only perform the following if the master process for the
    # region controller.
    if is_master_process():
        # Make sure that maas user's GNUPG home directory exists. This is
        # needed for importing of boot resources, which occurs on the region
        # as well as the clusters.
        create_gnupg_home()

        # If there are no boot-source definitions yet, create defaults.
        ensure_boot_source_definition()

        # Freshen the kms SRV records.
        dns_kms_setting_changed()
