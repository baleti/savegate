"""c5x-rvtgap item 111: 'deg' had no magnitude bound (1e308 and 2**70 passed _check_numbers; the other numeric keys are bounded to +-1e5 ft). Now +-3600 degrees, NaN/inf still refused. Pure input validation."""
import pytest
from savegate import rvt_writer_ops as WO


@pytest.mark.parametrize('v', [1e308, -1e308, 2 ** 70, 1e9, 3600.5, -3601, float('inf'), float('nan'), '5', True])
def test_absurd_deg_refused(v):
    with pytest.raises(ValueError): WO._check_numbers({'op': 'rotate_instance', 'id': 5, 'deg': v})


@pytest.mark.parametrize('v', [0, -0.0, 5, 90.0, -270, 360, 720, 3600])
def test_sane_deg_accepted(v):
    WO._check_numbers({'op': 'rotate_instance', 'id': 5, 'deg': v})
