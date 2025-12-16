"""Examine Effect of scaler RATE on T"""

import numpy as np
from apsbits.core.instrument_init import oregistry
from bluesky import plans as bp
from bluesky.utils import plan


@plan
def rate_effect(first=10, last=40, step=1, npts=10):
    """Measure the effect of scaler RATE on T."""
    scaler1 = oregistry["scaler1"]
    for rate in np.arange(first, last + step / 10, step):
        scaler1.update_rate.put(rate)

        yield from bp.count(
            [scaler1],
            num=npts,
            md=dict(
                TP=np.round(scaler1.preset_time.get(), 4),
                RATE=np.round(rate, 4),
                title=f"Effect of scaler RATE on T, {rate=:.2f}",
            ),
        )
