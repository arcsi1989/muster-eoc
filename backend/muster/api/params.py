"""Query parameters several routes share."""

from typing import Annotated

from fastapi import Query

AdvisoryQuery = Annotated[int, Query(ge=1)]  # an advisory number, 1 or more
