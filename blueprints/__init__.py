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

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(blog_feedback_bp)
    app.register_blueprint(tags_categories_bp)
    app.register_blueprint(trash_bp)
    app.register_blueprint(system_bp)
