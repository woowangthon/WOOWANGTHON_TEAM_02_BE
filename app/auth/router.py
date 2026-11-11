"""Jinja2 기반 회원가입·로그인 화면과 처리."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from psycopg.errors import UniqueViolation
from psycopg_pool import ConnectionPool

from app.auth.security import (
    ACCESS_TOKEN_MINUTES,
    create_access_token,
    hash_password,
    read_access_token,
    verify_password,
    verify_unknown_user_password,
)
from app.config import get_settings

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _pool(request: Request) -> ConnectionPool:
    return request.app.state.db_pool


def _render(
    request: Request,
    template_name: str,
    context: dict[str, Any],
    status_code: int = status.HTTP_200_OK,
) -> Any:
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
        status_code=status_code,
    )


def _registration_options(pool: ConnectionPool) -> dict[str, list[tuple[Any, ...]]]:
    with pool.connection() as conn:
        schools = conn.execute(
            "SELECT id, name FROM schools WHERE is_active ORDER BY name"
        ).fetchall()
        departments = conn.execute(
            """
            SELECT d.id, s.id, s.name, d.name,
                   coalesce(parent.name, '단과대학·학부') AS college_name
            FROM departments AS d
            JOIN schools AS s ON s.id = d.school_id
            LEFT JOIN departments AS parent
              ON parent.id = d.parent_id AND parent.school_id = d.school_id
            WHERE s.is_active
            ORDER BY s.name, college_name, d.name
            """
        ).fetchall()
        tags = conn.execute(
            """
            SELECT id, name
            FROM tags
            WHERE is_active AND is_user_selectable
            ORDER BY sort_order, name
            """
        ).fetchall()
    return {"schools": schools, "departments": departments, "tags": tags}


def _registration_page(
    request: Request,
    pool: ConnectionPool,
    *,
    error: str | None = None,
    email: str = "",
    school_id: int | None = None,
    department_id: int | None = None,
    grade: int | None = None,
    interest_ids: set[int] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Any:
    context: dict[str, Any] = _registration_options(pool)
    context.update(
        {
            "error": error,
            "email": email,
            "selected_school_id": school_id,
            "selected_department_id": department_id,
            "selected_grade": grade,
            "selected_interest_ids": interest_ids or set(),
        }
    )
    return _render(request, "register.html", context, status_code)


@router.get("/register", name="register")
def register_page(request: Request, pool: Annotated[ConnectionPool, Depends(_pool)]) -> Any:
    return _registration_page(request, pool)


@router.post("/register", name="register_submit")
def register_submit(
    request: Request,
    pool: Annotated[ConnectionPool, Depends(_pool)],
    email: Annotated[str, Form(min_length=3, max_length=320)],
    password: Annotated[str, Form(min_length=8, max_length=128)],
    school_id: Annotated[int, Form(gt=0)],
    department_id: Annotated[int, Form(gt=0)],
    grade: Annotated[int, Form(ge=1, le=6)],
    interest_ids: Annotated[list[int] | None, Form()] = None,
) -> Any:
    normalized_email = email.strip().lower()
    selected_interests = set(interest_ids or [])

    def render_error(message: str, response_status: int = status.HTTP_400_BAD_REQUEST) -> Any:
        return _registration_page(
            request,
            pool,
            error=message,
            email=normalized_email,
            school_id=school_id,
            department_id=department_id,
            grade=grade,
            interest_ids=selected_interests,
            status_code=response_status,
        )

    if not EMAIL_PATTERN.fullmatch(normalized_email):
        return render_error("이메일 주소를 확인해 주세요.")

    password_hash = hash_password(password)
    validation_error = None
    try:
        with pool.connection() as conn:
            department_belongs_to_school = conn.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM departments AS d
                    JOIN schools AS s ON s.id = d.school_id
                    WHERE d.id = %s AND s.id = %s AND s.is_active
                )
                """,
                (department_id, school_id),
            ).fetchone()[0]
            if not department_belongs_to_school:
                validation_error = "선택한 학교와 학과를 확인해 주세요."

            if selected_interests and validation_error is None:
                valid_interest_ids = {
                    row[0]
                    for row in conn.execute(
                        """
                        SELECT id
                        FROM tags
                        WHERE id = ANY(%s) AND is_active AND is_user_selectable
                        """,
                        (list(selected_interests),),
                    ).fetchall()
                }
                if valid_interest_ids != selected_interests:
                    validation_error = "선택할 수 없는 관심 분야가 포함되어 있습니다."

            if validation_error is None:
                user_id = conn.execute(
                    """
                    INSERT INTO users (email, password_hash, school_id, department_id, grade)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (normalized_email, password_hash, school_id, department_id, grade),
                ).fetchone()[0]
                if selected_interests:
                    with conn.cursor() as cursor:
                        cursor.executemany(
                            "INSERT INTO user_interests (user_id, tag_id) VALUES (%s, %s)",
                            [(user_id, tag_id) for tag_id in selected_interests],
                        )
    except UniqueViolation:
        return render_error("이미 가입된 이메일입니다.", status.HTTP_409_CONFLICT)

    if validation_error is not None:
        return render_error(validation_error)

    return RedirectResponse(url="/login?registered=1", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", name="login")
def login_page(request: Request, registered: bool = False) -> Any:
    return _render(
        request,
        "login.html",
        {"error": None, "registered": registered, "email": ""},
    )


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    pool: Annotated[ConnectionPool, Depends(_pool)],
    email: Annotated[str, Form(min_length=3, max_length=320)],
    password: Annotated[str, Form(min_length=1, max_length=128)],
) -> Any:
    normalized_email = email.strip().lower()
    if len(get_settings().jwt_secret.encode("utf-8")) < 32:
        return _render(
            request,
            "login.html",
            {
                "error": "로그인 설정이 완료되지 않았습니다. 관리자에게 문의해 주세요.",
                "registered": False,
                "email": normalized_email,
            },
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT id, password_hash
            FROM users
            WHERE lower(email) = %s AND status = 'active'
            """,
            (normalized_email,),
        ).fetchone()
        if row is None:
            verify_unknown_user_password(password)
            user_id = None
            password_is_valid = False
        else:
            user_id, password_hash = row
            password_is_valid = verify_password(password_hash, password)

        if not password_is_valid or user_id is None:
            return _render(
                request,
                "login.html",
                {
                    "error": "이메일 또는 비밀번호를 확인해 주세요.",
                    "registered": False,
                    "email": email,
                },
                status.HTTP_401_UNAUTHORIZED,
            )

        conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user_id,))

    token = create_access_token(user_id)
    response = RedirectResponse(url="/me", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=ACCESS_TOKEN_MINUTES * 60,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


def get_current_user(
    request: Request,
    pool: Annotated[ConnectionPool, Depends(_pool)],
) -> dict[str, Any]:
    token = request.cookies.get("access_token")
    user_id = read_access_token(token) if token else None
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")

    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.school_id, u.department_id, s.name, d.name, u.grade
            FROM users AS u
            JOIN schools AS s ON s.id = u.school_id
            JOIN departments AS d ON d.id = u.department_id
            WHERE u.id = %s AND u.status = 'active'
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
    return {
        "id": row[0],
        "email": row[1],
        "school_id": row[2],
        "department_id": row[3],
        "school": row[4],
        "department": row[5],
        "grade": row[6],
    }


@router.get("/me", name="profile")
def profile(
    request: Request,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> Any:
    return _render(request, "profile.html", {"user": user})


@router.post("/logout", name="logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax")
    return response
