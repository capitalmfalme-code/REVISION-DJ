# Developer Hub — Patch Package

Drop these files into your MFALME PREMIUM DOJO project at the matching paths
(they mirror your existing `dojo/` app structure). No other files were touched.

## SECTION 1 — UPDATED FILES
- dojo/models.py                              (added DevProject, DevAsset models)
- dojo/admin.py                               (registered the 2 new models)
- dojo/urls.py                                (added 9 new Developer Hub routes)
- dojo/templates/dojo/cbc_dashboard.html      (added "Developer Hub" nav item)
- dojo/templates/dojo/igcse_dashboard.html    (added "Developer Hub" nav item)
- dojo/templates/dojo/844_dashboard.html      (added "Developer Hub" nav item)

## SECTION 2 — NEW FILES
- dojo/developer_views.py                          (all Developer Hub views/API)
- dojo/templates/dojo/developer_dashboard.html      (Hub landing page)
- dojo/templates/dojo/developer_projects.html       (project list page)
- dojo/templates/dojo/developer_editor.html         (Monaco HTML/CSS/JS editor + live preview + asset upload)
- dojo/templates/dojo/developer_showcase.html       (public /showcase/<slug>/ page)

## SECTION 3 — MIGRATIONS
- dojo/migrations/0020_devproject_devasset.py

## Install steps
1. Copy the `dojo/` folder contents from this zip into your project's `dojo/` app,
   overwriting models.py, admin.py, urls.py, and the three dashboard templates.
2. Run: `python manage.py migrate`
3. Restart your server. Students will see "🚀 Developer Hub" in their dashboard
   top-nav (desktop) and mobile menu.

## Routes added
- GET  /developer/
- GET  /developer/projects/
- GET  /developer/project/new/
- GET  /developer/project/<id>/
- POST /developer/project/<id>/save/
- POST /developer/project/<id>/publish/
- POST /developer/project/<id>/upload/
- POST /developer/project/<id>/delete/   (extra — needed for the "Delete" requirement, not in your original route list)
- GET  /showcase/<slug>/                 (public, no login required)

## Notes
- All new views/models follow your existing conventions exactly: `require_role`,
  `ok()`/`err()`/`json_body()` helpers from views.py are reused (not duplicated),
  `LoginRequiredMixin`-style role checks, same CSS variables/fonts/buttons/cards
  as your existing dashboards, and the same client-side `api()`/`toast()` JS
  pattern already used in cbc_dashboard.html.
- Fully tested end-to-end with Django's test client: create → save → upload
  asset → publish → public showcase view → delete, plus role-gating (tutors/
  anon blocked), ownership checks (404 on cross-student access), and rejection
  of non-image uploads.
- Security note: the showcase page intentionally renders the student's raw
  HTML/CSS/JS (same model as CodePen/JSFiddle) since that's the entire point of
  "publish a runnable project." It is served from the same origin as the rest
  of the site. For Phase 2, consider serving `/showcase/` from a separate
  subdomain to fully sandbox student-authored JS from the main site's cookies.
