#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GizVFX - effects drawn from code (pixel sprites, and the same recipes painted smooth in 8 styles). Entry point: python gizvfx.py COMMAND ... (see `python gizvfx.py` for the list)."""
__version__ = "0.1.0"
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gizvfx.cli import main
sys.exit(main())
