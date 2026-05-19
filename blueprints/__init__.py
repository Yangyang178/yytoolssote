from flask import Blueprint


def register_blueprints(app):
    from .auth import auth_bp
    from .files import files_bp
    from .ai import ai_bp
    from .security import security_bp
    from .admin import admin_bp
    from .blog_feedback import blog_feedback_bp
    from .tags_categories import tags_categories_bp
    from .trash import trash_bp
    from .system import system_bp
    from .notification import notification_bp
    from .openapi import openapi_bp
    from .workspace import workspace_bp
    from .comments import comments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(blog_feedback_bp)
    app.register_blueprint(tags_categories_bp)
    app.register_blueprint(trash_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(openapi_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(comments_bp)

    endpoint_map = {}
    for rule in list(app.url_map.iter_rules()):
        if '.' in rule.endpoint:
            old_ep = rule.endpoint
            new_ep = old_ep.split('.', 1)[1]
            endpoint_map[old_ep] = new_ep

    for old_ep, new_ep in endpoint_map.items():
        if new_ep not in app.view_functions:
            app.view_functions[new_ep] = app.view_functions[old_ep]
        if old_ep in app.view_functions:
            del app.view_functions[old_ep]

    if hasattr(app.url_map, '_rules_by_endpoint'):
        new_rules_by_endpoint = {}
        for ep, rules in app.url_map._rules_by_endpoint.items():
            new_ep = endpoint_map.get(ep, ep)
            for rule in rules:
                rule.endpoint = new_ep
            new_rules_by_endpoint[new_ep] = rules
        app.url_map._rules_by_endpoint = new_rules_by_endpoint
    else:
        for rule in list(app.url_map.iter_rules()):
            if '.' in rule.endpoint:
                rule.endpoint = rule.endpoint.split('.', 1)[1]
