"""
Start Bluesky Data Acquisition sessions of all kinds.

Includes:

* Python script
* IPython console
* Jupyter notebook
* Bluesky queueserver
"""

# Standard Library Imports
import logging
import os
from pathlib import Path

# ------ resume
# Core Functions
from apsbits.core.best_effort_init import init_bec_peaks
from apsbits.core.catalog_init import init_catalog
from apsbits.core.instrument_init import init_instrument
from apsbits.core.instrument_init import make_devices
from apsbits.core.run_engine_init import init_RE

# Utility functions
from apsbits.utils.aps_functions import host_on_aps_subnet
from apsbits.utils.baseline_setup import setup_baseline_stream

# Configuration functions
from apsbits.utils.config_loaders import load_config
from apsbits.utils.helper_functions import register_bluesky_magics

# TODO: see below, apsbits #184
# from apsbits.utils.helper_functions import running_in_queueserver
from apsbits.utils.logging_setup import configure_logging

# Configuration block
# Get the path to the instrument package
# Load configuration to be used by the instrument.
instrument_path = Path(__file__).parent
iconfig_path = instrument_path / "configs" / "iconfig.yml"
iconfig = load_config(iconfig_path)

# Additional logging configuration
# only needed if using different logging setup
# from the one in the apsbits package
extra_logging_configs_path = instrument_path / "configs" / "extra_logging.yml"
configure_logging(extra_logging_configs_path=extra_logging_configs_path)


logger = logging.getLogger(__name__)
logger.info("Starting Instrument with iconfig: %s", iconfig_path)

# initialize instrument
instrument, oregistry = init_instrument("guarneri")

# Discard oregistry items loaded above.
oregistry.clear()

# Configure the session with callbacks, devices, and plans.
# aps_dm_setup(iconfig.get("DM_SETUP_FILE"))

# Command-line tools, such as %wa, %ct, ...
register_bluesky_magics()

# Bluesky initialization block

if iconfig.get("TILED_PROFILE_NAME", {}):
    from tiled.client import from_profile

    profile_name = iconfig.get("TILED_PROFILE_NAME")
    tiled_client = from_profile(profile_name)

bec, peaks = init_bec_peaks(iconfig)
cat = init_catalog(iconfig)
RE, sd = init_RE(iconfig, subscribers=[bec, cat])

if iconfig.get("TILED_PROFILE_NAME", {}) == {}:
    """Also publish document through tiled to PostgreSQL."""
    from bluesky_tiled_plugins import TiledWriter
    from tiled.client import from_profile

    logging.getLogger("httpx").setLevel(logging.WARNING)
    profile_name = "demo1"
    tiled_client = from_profile(profile_name)
    tiled_cat = tiled_client["/raw"]
    tw = TiledWriter(tiled_cat, batch_size=1)
    RE.subscribe(tw)

# Optional Nexus callback block
# delete this block if not using Nexus
if iconfig.get("NEXUS_DATA_FILES", {}).get("ENABLE", False):
    from .callbacks.demo_nexus_callback import nxwriter_init

    nxwriter = nxwriter_init(RE)

# Optional SPEC callback block
# delete this block if not using SPEC
if iconfig.get("SPEC_DATA_FILES", {}).get("ENABLE", False):
    from .callbacks.demo_spec_callback import init_specwriter_with_RE
    from .callbacks.demo_spec_callback import newSpecFile  # noqa: F401
    from .callbacks.demo_spec_callback import spec_comment  # noqa: F401
    from .callbacks.demo_spec_callback import specwriter  # noqa: F401

    init_specwriter_with_RE(RE)


def running_in_queueserver() -> bool:
    """Replaces function in apsbits.utils.helper_functions."""
    # apsbits #184
    keys = """
        QS_CONFIG_YML
        _QSERVER_RE_WORKER_ACTIVE
        _QSERVER_RUNNING_IPYTHON_KERNEL
    """.split()
    for key in keys:
        if os.environ.get(key) is not None:
            return True
    return False


# These imports must come after the above setup.
# Queue server block
if running_in_queueserver():
    ### To make all the standard plans available in QS, import by '*', otherwise import
    ### plan by plan.
    from apstools.plans import lineup2  # noqa: F401
    from bits2511.plans.gp_device_setup import change_noisy_signal_parameters  # noqa: F401
    from bluesky.plans import *  # noqa: F403

    logger.info("Queueserver session")
else:
    # Import bluesky plans and stubs with prefixes set by common conventions.
    # The apstools plans and utils are imported by '*'.
    from apstools.plans import *  # noqa: F403
    from apstools.utils import *  # noqa: F403
    from bluesky import plan_stubs as bps  # noqa: F401
    from bluesky import plans as bp  # noqa: F401

    logger.info("Interactive session")

# Experiment specific logic, device and plan loading. # Create the devices.
make_devices(clear=False, file="devices.yml", device_manager=instrument)

if host_on_aps_subnet():
    make_devices(clear=False, file="devices_aps_only.yml", device_manager=instrument)

try:
    import gi
    import hklpy2
    from hklpy2.backends.hkl_soleil import libhkl

    version_md = RE.md["versions"]
    version_md["gi"] = gi.__version__  # ".".join(map(str, gi.version_info))
    # FIXME: gi._versions is a dict that does not validate in event_model
    # version_md["gi._versions"] = gi._versions
    version_md["hklpy2"] = hklpy2.__version__
    version_md["libhkl"] = libhkl.VERSION

    make_devices(clear=False, file="diffractometers.yml", device_manager=instrument)
except (ImportError, ModuleNotFoundError) as exinfo:
    print(f"No hklpy2 diffractometers: {exinfo=}")

# Setup baseline stream with connect=False is default
# Devices with the label 'baseline' will be added to the baseline stream.
setup_baseline_stream(sd, oregistry, connect=False)

sd.monitors.append(oregistry["temperature"])  # TODO: via label, like baseline?

from .plans.sim_plans import sim_count_plan  # noqa: E402, F401
from .plans.sim_plans import sim_print_plan  # noqa: E402, F401
from .plans.sim_plans import sim_rel_scan_plan  # noqa: E402, F401

# ---------------------------
# --------------------------- local changes
# ---------------------------

# adjust the scan_id to the current catalog
oregistry["scan_id_epics"].put(len(cat))


def on_startup():
    """Custom session initialization."""
    from bits2511.plans.gp_device_setup import _custom_controls_setup

    yield from _custom_controls_setup()


RE(on_startup())
