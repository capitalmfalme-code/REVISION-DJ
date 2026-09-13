"""
dojo/developer_views.py
------------------------
Developer Hub — Phase 1 with Admin Suspension Controls + Multi-file support.

Lets authenticated students create, edit, save, preview, and publish
simple HTML/CSS/JS projects from their own dashboard. Published projects
get a public, shareable showcase URL at /showcase/<slug>/.

Admins can suspend/restore individual student's developer access.
"""

from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction

from .models import DevProject, DevAsset, DevFile, User
from .views import ok, err, json_body, require_role

MAX_ASSET_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_ASSET_TYPES = (
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/svg+xml",
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _project_json(project, include_files=False):
    data = {
        "id": project.id,
        "title": project.title,
        "slug": project.slug,
        "html_code": project.html_code,
        "css_code": project.css_code,
        "js_code": project.js_code,
        "is_published": project.is_published,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "showcase_url": project.showcase_url,
    }
    if include_files:
        data["files"] = [
            {
                "id": f.id,
                "path": f.path,
                "content": f.content,
                "is_entry": f.is_entry,
                "language": f.language,
                "updated_at": f.updated_at.isoformat(),
            }
            for f in project.files.all()
        ]
    return data


def _asset_json(asset):
    """Serialise a DevAsset, deriving its project-relative path."""
    folder = getattr(asset, "folder", "") or ""
    filename = asset.original_filename or asset.file.name.split("/")[-1]
    path = f"{folder}/{filename}" if folder else filename
    return {
        "id": asset.id,
        "url": asset.file.url,
        "name": filename,
        "path": path,
    }


def _sync_legacy_fields(project):
    """
    Keep DevProject.html_code/css_code/js_code in sync with the primary
    files in DevFile. This means showcase.html and the admin views that
    read the legacy fields keep working without changes.
    """
    entry = project.files.filter(is_entry=True).first() \
        or project.files.filter(path__endswith='.html').first()

    css = project.files.filter(path__endswith='.css').first()
    js = project.files.filter(path__endswith='.js').first()

    changed = False
    if entry and project.html_code != entry.content:
        project.html_code = entry.content
        changed = True
    if css and project.css_code != css.content:
        project.css_code = css.content
        changed = True
    if js and project.js_code != js.content:
        project.js_code = js.content
        changed = True

    if changed:
        project.save(update_fields=['html_code', 'css_code', 'js_code'])


# ─────────────────────────────────────────────────────────────────────────────
# DEVELOPER ACCESS DECORATORS
# ─────────────────────────────────────────────────────────────────────────────

def require_developer_access(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dojo:login')
        if request.user.role != 'student':
            return redirect('dojo:home')
        if request.user.developer_access_suspended:
            suspended_by = request.user.developer_suspended_by
            context = {
                'reason': request.user.developer_suspension_reason,
                'suspended_at': request.user.developer_suspended_at,
                'suspended_by': suspended_by.get_full_name() or suspended_by.username if suspended_by else None,
            }
            return render(request, 'dojo/developer_suspended.html', context, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_developer_access_api(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return err("Authentication required", 401)
        if request.user.role != 'student':
            return err("Student access required", 403)
        if request.user.developer_access_suspended:
            return err("Developer access has been suspended", 403)
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# HTML PAGES
# ─────────────────────────────────────────────────────────────────────────────

class DeveloperHubView(View):
    """Developer Hub landing page — entry point from the student dashboard."""

    @method_decorator(require_developer_access)
    def get(self, request):
        all_projects = DevProject.objects.filter(user=request.user)
        published_count = all_projects.filter(is_published=True).count()
        project_count = all_projects.count()
        context = {
            "recent_projects": all_projects.order_by('-updated_at')[:6],
            "project_count": project_count,
            "published_count": published_count,
            "draft_count": project_count - published_count,
        }
        return render(request, "dojo/developer_dashboard.html", context)


class DeveloperProjectListView(View):
    """Lists every project belonging to the logged-in student."""

    @method_decorator(require_developer_access)
    def get(self, request):
        projects = DevProject.objects.filter(user=request.user).order_by('-updated_at')
        return render(request, "dojo/developer_projects.html", {"projects": projects})


class DeveloperProjectCreateView(View):
    """
    GET  → show the name-your-project form
    POST → create empty project (no starter files), redirect to editor
    """

    @method_decorator(require_developer_access)
    def get(self, request):
        return render(request, "dojo/developer_project_new.html")

    @method_decorator(require_developer_access)
    def post(self, request):
        title = (request.POST.get("title") or "").strip() or "Untitled Project"
        title = title[:150]

        with transaction.atomic():
            project = DevProject.objects.create(user=request.user, title=title)

        return redirect('dojo:developer_editor', project_id=project.id)


class DeveloperProjectEditorView(View):
    """The Monaco-powered editor. Students build everything from scratch."""

    @method_decorator(require_developer_access)
    def get(self, request, project_id):
        project = get_object_or_404(DevProject, id=project_id, user=request.user)
        return render(request, "dojo/developer_editor.html", {"project": project})


class DeveloperProjectDeleteView(View):
    """Deletes one of the student's own projects. Triggered from the project list."""

    @method_decorator(require_developer_access)
    def post(self, request, project_id):
        project = get_object_or_404(DevProject, id=project_id, user=request.user)
        project.delete()
        return redirect('dojo:developer_projects')


class DeveloperShowcaseView(View):
    """Public, read-only page rendering a student's published project."""

    def get(self, request, slug):
        project = get_object_or_404(DevProject, slug=slug, is_published=True)
        return render(request, "dojo/developer_showcase.html", {"project": project})


# ─────────────────────────────────────────────────────────────────────────────
# AJAX API — PROJECT
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_project_save(request, project_id):
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    data = json_body(request)

    title = (data.get("title") or "").strip()
    if title:
        project.title = title[:150]

    if "html_code" in data:
        project.html_code = data.get("html_code") or ""
    if "css_code" in data:
        project.css_code = data.get("css_code") or ""
    if "js_code" in data:
        project.js_code = data.get("js_code") or ""

    project.save()
    return ok(project=_project_json(project))


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_project_publish(request, project_id):
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    data = json_body(request)
    action = data.get("action", "publish")

    _sync_legacy_fields(project)

    if action == "unpublish":
        project.is_published = False
        project.save(update_fields=["is_published"])
        return ok(project=_project_json(project))

    if not project.slug:
        project.slug = project.generate_unique_slug()
    project.is_published = True
    project.save()
    return ok(project=_project_json(project))


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_project_upload(request, project_id):
    """Upload an image into the project (root or a folder)."""
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    file = request.FILES.get("file")
    folder = (request.POST.get("folder") or "").strip().strip("/")

    if not file:
        return err("No file provided", 400)
    if file.size > MAX_ASSET_SIZE:
        return err("File too large. Max 5MB", 400)
    if file.content_type not in ALLOWED_ASSET_TYPES:
        return err("Only image files are allowed (PNG, JPG, GIF, WEBP, SVG)", 400)

    asset = DevAsset.objects.create(
        project=project,
        file=file,
        original_filename=file.name,
    )

    # Persist folder on the asset if the model supports it
    if hasattr(asset, "folder") and folder:
        asset.folder = folder
        asset.save(update_fields=["folder"])

    filename = asset.original_filename or file.name
    file_path = f"{folder}/{filename}" if folder else filename

    return ok(
        id=asset.id,
        url=asset.file.url,
        name=filename,
        path=file_path,
    )


# ─────────────────────────────────────────────────────────────────────────────
# AJAX API — FILES
# ─────────────────────────────────────────────────────────────────────────────

@require_role("student")
@require_developer_access_api
def api_developer_files_list(request, project_id):
    """Return all code files in a project."""
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    return ok(files=[
        {
            "id": f.id,
            "path": f.path,
            "content": f.content,
            "is_entry": f.is_entry,
            "language": f.language,
            "updated_at": f.updated_at.isoformat(),
        }
        for f in project.files.all()
    ])


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_file_create(request, project_id):
    """Create a new empty file. Path may contain slashes to create folders."""
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    data = json_body(request)

    path = (data.get("path") or "").strip().lstrip("/")
    if not path:
        return err("File name required", 400)
    if len(path) > 255:
        return err("File name too long", 400)
    if ".." in path:
        return err("Invalid path", 400)
    if project.files.filter(path=path).exists():
        return err(f"'{path}' already exists", 409)

    is_entry = False
    if path.endswith(('.html', '.htm')) and not project.files.filter(is_entry=True).exists():
        is_entry = True

    f = project.files.create(
        path=path,
        content=data.get("content", ""),
        is_entry=is_entry,
    )
    return ok(file={
        "id": f.id,
        "path": f.path,
        "content": f.content,
        "is_entry": f.is_entry,
        "language": f.language,
    })


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_file_save(request, file_id):
    """Save a file's content (and optionally rename it)."""
    f = get_object_or_404(DevFile, id=file_id, project__user=request.user)
    data = json_body(request)

    if "content" in data:
        f.content = data.get("content") or ""

    new_path = (data.get("path") or "").strip().lstrip("/")
    if new_path and new_path != f.path:
        if len(new_path) > 255 or ".." in new_path:
            return err("Invalid path", 400)
        if f.project.files.exclude(pk=f.pk).filter(path=new_path).exists():
            return err(f"'{new_path}' already exists", 409)
        f.path = new_path

    f.save()

    if f.is_entry:
        _sync_legacy_fields(f.project)

    return ok(file={
        "id": f.id,
        "path": f.path,
        "content": f.content,
        "is_entry": f.is_entry,
        "language": f.language,
        "updated_at": f.updated_at.isoformat(),
    })


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_file_rename(request, file_id):
    """Rename or move a file."""
    f = get_object_or_404(DevFile, id=file_id, project__user=request.user)
    new_path = (json_body(request).get("path") or "").strip().strip("/")
    if not new_path or ".." in new_path:
        return err("Invalid path", 400)
    if f.project.files.exclude(pk=f.pk).filter(path=new_path).exists():
        return err("A file with that path already exists", 409)
    f.path = new_path
    f.save()
    if f.is_entry:
        _sync_legacy_fields(f.project)
    return ok(file={"id": f.id, "path": f.path})


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_file_delete(request, file_id):
    """Delete a file from the project."""
    f = get_object_or_404(DevFile, id=file_id, project__user=request.user)
    project = f.project
    was_entry = f.is_entry
    f.delete()

    if was_entry:
        replacement = project.files.filter(path__endswith='.html').first() \
                   or project.files.first()
        if replacement:
            replacement.is_entry = True
            replacement.save(update_fields=['is_entry'])
            _sync_legacy_fields(project)

    return ok()


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_file_set_entry(request, file_id):
    """Mark a file as the entry (preview target)."""
    f = get_object_or_404(DevFile, id=file_id, project__user=request.user)
    f.project.files.update(is_entry=False)
    f.is_entry = True
    f.save(update_fields=['is_entry'])
    _sync_legacy_fields(f.project)
    return ok()


# ─────────────────────────────────────────────────────────────────────────────
# AJAX API — ASSETS (uploaded images)
# ─────────────────────────────────────────────────────────────────────────────

@require_role("student")
@require_developer_access_api
def api_developer_assets_list(request, project_id):
    """Return all uploaded images for a project."""
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    return ok(assets=[_asset_json(a) for a in project.assets.all()])


@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_asset_delete(request, asset_id):
    """Delete an uploaded image from the project."""
    asset = get_object_or_404(DevAsset, id=asset_id, project__user=request.user)
    try:
        asset.file.delete(save=False)
    except Exception:
        pass
    asset.delete()
    return ok()


# ─────────────────────────────────────────────────────────────────────────────
# AJAX API — FOLDERS (virtual)
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
@require_role("student")
@require_developer_access_api
def api_developer_folder_create(request, project_id):
    """
    Folders are virtual — they exist as long as a file or asset lives inside
    them. The frontend keeps track of empty folders in the current session.
    We just validate and echo back.
    """
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    path = (json_body(request).get("path") or "").strip().strip("/")
    if not path or ".." in path:
        return err("Invalid folder path", 400)
    return ok(path=path)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN API — Developer Access Control
# ─────────────────────────────────────────────────────────────────────────────

@require_role("admin")
def api_admin_developer_suspend(request, user_id):
    """Admin endpoint to suspend a student's developer access."""
    user = get_object_or_404(User, id=user_id, role='student')

    if user.developer_access_suspended:
        return err("User already suspended", 400)

    data = json_body(request)
    reason = data.get("reason", "").strip()

    user.suspend_developer_access(
        admin_user=request.user,
        reason=reason or "No reason provided"
    )

    return ok(
        user_id=user.id,
        email=user.email,
        name=user.get_full_name() or user.username,
        suspended=True,
        reason=user.developer_suspension_reason,
        suspended_at=user.developer_suspended_at.isoformat() if user.developer_suspended_at else None,
        suspended_by=request.user.get_full_name() or request.user.username,
    )


@require_role("admin")
def api_admin_developer_restore(request, user_id):
    """Admin endpoint to restore a student's developer access."""
    user = get_object_or_404(User, id=user_id, role='student')

    if not user.developer_access_suspended:
        return err("User not suspended", 400)

    user.restore_developer_access(admin_user=request.user)

    return ok(
        user_id=user.id,
        email=user.email,
        name=user.get_full_name() or user.username,
        suspended=False,
        restored_at=user.developer_restored_at.isoformat() if user.developer_restored_at else None,
        restored_by=request.user.get_full_name() or request.user.username,
    )


@require_role("admin")
def api_admin_developer_suspended_list(request):
    """Admin endpoint to list all students with suspended developer access."""
    users = User.objects.filter(
        role='student',
        developer_access_suspended=True
    ).select_related('developer_suspended_by')

    result = []
    for u in users:
        result.append({
            "id": u.id,
            "email": u.email,
            "name": u.get_full_name() or u.username,
            "reason": u.developer_suspension_reason,
            "suspended_at": u.developer_suspended_at.isoformat() if u.developer_suspended_at else None,
            "suspended_by": u.developer_suspended_by.get_full_name() or u.developer_suspended_by.username if u.developer_suspended_by else None,
        })

    return ok(suspended_users=result)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN API — Developer Projects
# ─────────────────────────────────────────────────────────────────────────────

@require_role("admin")
def api_admin_developer_projects(request):
    """Admin endpoint to list all developer projects."""
    projects = DevProject.objects.select_related('user').order_by('-updated_at')

    result = []
    for p in projects:
        data = _project_json(p)
        data.update({
            "user_name": p.user.get_full_name() or p.user.username,
            "user_email": p.user.email,
            "developer_access_suspended": p.user.developer_access_suspended,
            "file_count": p.files.count(),
            "asset_count": p.assets.count(),
        })
        result.append(data)

    return ok(projects=result)


@require_role("admin")
def api_admin_developer_project_detail(request, project_id):
    """Admin endpoint to get full project details including code and assets."""
    project = get_object_or_404(DevProject, id=project_id)

    user_name = project.user.get_full_name() or project.user.username
    user_email = project.user.email

    result = _project_json(project, include_files=True)
    result.update({
        "user_name": user_name,
        "user_email": user_email,
        "developer_access_suspended": project.user.developer_access_suspended,
        "html_code": project.html_code,
        "css_code": project.css_code,
        "js_code": project.js_code,
        "assets": [_asset_json(a) for a in project.assets.all()],
    })
    return ok(project=result)


@require_role("admin")
def api_admin_developer_project_delete(request, project_id):
    """Admin endpoint to delete any developer project."""
    project = get_object_or_404(DevProject, id=project_id)
    project.delete()
    return ok()