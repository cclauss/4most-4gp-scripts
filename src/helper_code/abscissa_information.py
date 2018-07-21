# -*- coding: utf-8 -*-

"""
Metadata data about all of the horizontal axes that we can plot precision against. When invoking any of the
<offset_*.py> scripts, the argument "abscissa_label" should be one of the keys to this dictionary.
"""


class AbcissaInformation:
    """
    Metadata data about all of the horizontal axes that we can plot precision against. When invoking any of the
    <offset_*.py> scripts, the argument "abscissa_label" should be one of the keys to this dictionary.
    """

    def __init__(self):
        self.abscissa_labels = {
            # label name, latex label, log axes, axis range
            "SNR/A": {"field": "SNR",
                      "latex": "$S/N$ $[{\\rm \\AA}^{-1}]$",
                      "log_axis": False,
                      "axis_range": (0, 250)},
            "SNR/pixel": {"field": "SNR",
                          "latex": "$S/N$ $[{\\rm pixel}^{-1}]$",
                          "log_axis": False,
                          "axis_range": (0, 250)},
            "ebv": {"field": "e_bv",
                    "latex": "$E(B-V)$",
                    "log_axis": True,
                    "axis_range": (0.04, 3)},
            "rv": {"field": "rv",
                   "latex": "RV [m/s]",
                   "log_axis": True,
                   "axis_range": (800, 50e3)}
        }