def generate_dynamic_content(project, module, component, message):
    return f"""
    <h2>{project.title()} - {module.capitalize()} - {component.upper()}</h2>
    <p><strong>Update from commit:</strong></p>
    <blockquote>{message}</blockquote>
    """
