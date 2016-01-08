#
# @file slib/slib.mk
# @version 0.2.0
#
# @section License
# Copyright (C) 2014-2016, Erik Moqvist
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# This file is part of the Simba project.
#


INC += $(SIMBA_ROOT)/src/slib

SLIB_SRC ?= crc.c \
            fat16.c \
            harness.c \
            hash_map.c \
            midi.c

SRC += $(SLIB_SRC:%=$(SIMBA_ROOT)/src/slib/%)
