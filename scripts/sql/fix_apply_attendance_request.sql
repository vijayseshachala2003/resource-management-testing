-- Fix attendance_request trigger function to handle request_type safely
-- and map SICK_LEAVE/FULL_DAY/HALF_DAY to LEAVE attendance_status

CREATE OR REPLACE FUNCTION public.apply_attendance_request(req_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    d DATE;
BEGIN
    SELECT * INTO r
    FROM public.attendance_requests
    WHERE id = req_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Guard: attendance_daily.project_id is NOT NULL
    IF r.project_id IS NULL THEN
        RETURN;
    END IF;

    FOR d IN
        SELECT generate_series(r.start_date, r.end_date, interval '1 day')::date
    LOOP
        INSERT INTO public.attendance_daily (
            user_id,
            project_id,
            attendance_date,
            status,
            request_id,
            source,
            notes
        )
        VALUES (
            r.user_id,
            r.project_id,
            d,
            CASE
                WHEN r.request_type::text IN ('SICK_LEAVE', 'FULL_DAY', 'HALF_DAY') THEN 'LEAVE'::public.attendance_status
                WHEN r.request_type::text = 'WFH' THEN 'PRESENT'::public.attendance_status
                ELSE 'UNKNOWN'::public.attendance_status
            END,
            r.id,
            'REQUEST_APPLY',
            r.reason
        )
        ON CONFLICT (user_id, project_id, attendance_date)
        DO UPDATE SET
            request_id = EXCLUDED.request_id,
            status = CASE
                WHEN COALESCE(public.attendance_daily.minutes_worked, 0) > 0 THEN public.attendance_daily.status
                ELSE EXCLUDED.status
            END,
            source = 'REQUEST_APPLY',
            notes = COALESCE(EXCLUDED.notes, public.attendance_daily.notes),
            updated_at = now();
    END LOOP;
END;
$$;

