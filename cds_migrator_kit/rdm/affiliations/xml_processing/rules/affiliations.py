# -*- coding: utf-8 -*-
#
# This file is part of CERN Document Server.
# Copyright (C) 2024 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""Common RDM fields."""

from cds_migrator_kit.transform.xml_processing.quality.contributors import (
    get_contributor_affiliations,
)
from cds_migrator_kit.transform.xml_processing.quality.decorators import (
    for_each_value,
    require,
)

# ATTENTION when COPYING! important which model you use as decorator
from ..models.affiliations import affiliation_model as model


def process_creatibutors(value):
    """Common function to process contributors."""
    affiliations = get_contributor_affiliations(value)
    contributor = {}

    if affiliations:
        contributor.update({"affiliations": affiliations})

    return contributor


@model.over("creators", "^100__")
@for_each_value
@require(["a"])
def creators(self, key, value):
    """Translates the creators field."""
    process_creatibutors(value)


@model.over("contributors", "(^700__)|(^701__)")
@for_each_value
@require(["a"])
def contributors(self, key, value):
    """Translates contributors."""
    return process_creatibutors(value)
