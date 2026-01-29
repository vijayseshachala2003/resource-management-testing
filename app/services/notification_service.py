import os
from typing import Optional

import requests


def send_attendance_request_decision_email(
    *,
    user_email: str,
    user_name: str,
    decision: str,
    comment: Optional[str],
    request_type: str,
    start_date: str,
    end_date: str,
    requester_name: Optional[str] = None,
    project_names: Optional[str] = None,
) -> None:
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_role_key:
        # Supabase Function not configured; skip email send.
        return

    function_url = f"{supabase_url}/functions/v1/send-approval-email"
    payload = {
        "email": user_email,
        "name": user_name,
        "decision": decision,
        "comment": comment or "",
        "request_type": request_type,
        "start_date": start_date,
        "end_date": end_date,
    }
    if requester_name:
        payload["requester_name"] = requester_name
    if project_names:
        payload["project_names"] = project_names

    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }

    try:
        requests.post(function_url, json=payload, headers=headers, timeout=10)
    except Exception:
        # Avoid breaking approval flow on email failures
        return


def send_attendance_request_created_email(
    *,
    recipient_email: str,
    recipient_name: str,
    requester_name: str,
    request_type: str,
    start_date: str,
    end_date: str,
    reason: Optional[str],
    project_names: Optional[str],
) -> None:
    send_attendance_request_decision_email(
        user_email=recipient_email,
        user_name=recipient_name or recipient_email,
        decision="REQUESTED",
        comment=reason,
        request_type=request_type,
        start_date=start_date,
        end_date=end_date,
        requester_name=requester_name,
        project_names=project_names,
    )

