def project_section(section: dict) -> dict:
    return {
        name: {
            k: v for k, v in control.items() if k not in {"node", "target", "bypass"}
        }
        for name, control in section.items()
    }
