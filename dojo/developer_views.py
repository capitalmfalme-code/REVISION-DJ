"""
dojo/developer_views.py
------------------------
Developer Hub — Phase 1.

Lets authenticated students create, edit, save, preview, and publish
simple HTML/CSS/JS projects from their own dashboard. Published projects
get a public, shareable showcase URL at /showcase/<slug>/.

No AI features. No collaboration features. No payment features.

Reuses the existing json_body / ok / err / require_role helpers already
defined in dojo/views.py so this module follows the same conventions as
the rest of the codebase without touching the existing views.py file.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import DevProject, DevAsset
from .views import ok, err, json_body, require_role

MAX_ASSET_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_ASSET_TYPES = (
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/svg+xml",
)


def _project_json(project):
    return {
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


# ─────────────────────────────────────────────────────────────────────────────
# HTML PAGES
# ─────────────────────────────────────────────────────────────────────────────

class DeveloperHubView(View):
    """Developer Hub landing page — entry point from the student dashboard."""
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('dojo:login')
        if request.user.role != 'student':
            return redirect('dojo:home')

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
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('dojo:login')
        if request.user.role != 'student':
            return redirect('dojo:home')

        projects = DevProject.objects.filter(user=request.user).order_by('-updated_at')
        return render(request, "dojo/developer_projects.html", {"projects": projects})


class DeveloperProjectCreateView(View):
    """Creates a brand-new blank project then sends the student straight into the editor."""
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('dojo:login')
        if request.user.role != 'student':
            return redirect('dojo:home')

        project = DevProject.objects.create(
            user=request.user,
            title="Untitled Project",
            html_code="<h1>Hello, World!</h1>\n<p>Start building your project here.</p>",
            css_code="body {\n  font-family: sans-serif;\n  padding: 24px;\n  color: #1a2638;\n}",
            js_code="// Your JavaScript goes here\nconsole.log('Project loaded');",
        )
        return redirect('dojo:developer_editor', project_id=project.id)


class DeveloperProjectEditorView(View):
    """The Monaco-powered HTML / CSS / JavaScript editor with live preview."""
    def get(self, request, project_id):
        if not request.user.is_authenticated:
            return redirect('dojo:login')
        if request.user.role != 'student':
            return redirect('dojo:home')

        project = get_object_or_404(DevProject, id=project_id, user=request.user)
        return render(request, "dojo/developer_editor.html", {"project": project})


class DeveloperProjectDeleteView(View):
    """Deletes one of the student's own projects. Triggered from the project list."""
    def post(self, request, project_id):
        if not request.user.is_authenticated:
            return redirect('dojo:login')
        if request.user.role != 'student':
            return redirect('dojo:home')

        project = get_object_or_404(DevProject, id=project_id, user=request.user)
        project.delete()
        return redirect('dojo:developer_projects')


class DeveloperShowcaseView(View):
    """Public, read-only page rendering a student's published project."""
    def get(self, request, slug):
        project = get_object_or_404(DevProject, slug=slug, is_published=True)
        return render(request, "dojo/developer_showcase.html", {"project": project})


# ─────────────────────────────────────────────────────────────────────────────
# AJAX API
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
@require_role("student")
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
def api_developer_project_publish(request, project_id):
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    data = json_body(request)
    action = data.get("action", "publish")

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
def api_developer_project_upload(request, project_id):
    project = get_object_or_404(DevProject, id=project_id, user=request.user)
    file = request.FILES.get("file")

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
    return ok(id=asset.id, url=asset.file.url, name=asset.original_filename)
