from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ConsumeQuery:
    """Query parameters kept separate from authentication and transport."""

    start_date: date
    end_date: date
    campus_id: Optional[str] = None
    subject_id: Optional[str] = None
    page_size: int = 1000
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_form(self) -> Dict[str, Any]:
        """Build the form used by the observed QueryConsumeTotalPro call."""
        payload: Dict[str, Any] = {
            "sDate": self.start_date.isoformat(),
            "eDate": self.end_date.isoformat(),
            "campusids": self.campus_id or "",
            "desc": 1,
            "dataType": "CampusName",
            "sort": "TotalMoney",
            "includeDullConsume": True,
            "shiftName": "",
            "shiftID": "",
            "PageCount": 1,
            "TotalCount": 1,
            "PageSize": self.page_size,
            "PageIndex": 1,
            "Subject": "",
            "Year": "",
            "Term": "",
            "Grade": "",
            "Category": "",
            "IncludeDullConsume": True,
        }
        if self.subject_id:
            payload["Subject"] = self.subject_id
        payload.update(self.extra)
        return payload


@dataclass(frozen=True)
class ScheduleQuery:
    """排课列表请求体；不包含任何登录凭据。"""

    start_date: date
    end_date: date
    campus_ids: List[str] = field(default_factory=list)
    page_index: int = 1
    page_size: int = 1000
    total_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> Dict[str, Any]:
        """Build the JSON body used by ``Course/QueryNew``."""
        zero_uuid = "00000000-0000-0000-0000-000000000000"
        payload: Dict[str, Any] = {
            "Afternoon": 1,
            "AssistantRoleTypeID": "",
            "AssistantTeacherIDList": [],
            "CampusIDList": list(self.campus_ids),
            "CategoryID": zero_uuid,
            "ClassIDList": [],
            "ClassLabelIDList": [],
            "ClassName": "",
            "ClassTypeID": zero_uuid,
            "ClassroomIDList": [],
            "CourseFlag": "",
            "CourseNumbers": 0,
            "CourseSubjectID": zero_uuid,
            "CourseType": 0,
            "CreateUserID": zero_uuid,
            "DialogType": 0,
            "Download": 0,
            "EndDate": self.end_date.isoformat(),
            "ExportColumn": [],
            "FinishType": "-1",
            "Forenoon": 1,
            "GradeID": zero_uuid,
            "HeadMasterUserIDList": [],
            "IncludeFull": 0,
            "IsContainFinished": -1,
            "IsSubscribeCourse": -1,
            "IsTotal": 0,
            "MasterIDList": [],
            "Nightnoon": 1,
            "PageIndex": self.page_index,
            "PageSize": self.page_size,
            "Query": "",
            "ShiftIDList": [],
            "ShiftTypeList": [],
            "ShowField": "",
            "StartDate": self.start_date.isoformat(),
            "StudentIDList": [],
            "SubjectID": zero_uuid,
            "TeacherIDList": [],
            "TeacherType": -1,
            "TermID": zero_uuid,
            "TotalCount": self.total_count,
            "TryStatus": 0,
            "UsePlatform": 0,
            "Weekdays": "",
            "Year": 0,
            "desc": 0,
            "sort": "Duration",
        }
        payload.update(self.extra)
        return payload
