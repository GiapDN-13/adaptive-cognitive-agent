# Security Rules

- **Container Isolation**: You are running in an isolated Docker container. You have root access inside the container, but any sensitive data or configurations outside the container cannot be touched.
- **Destructive Operations**: Be extremely careful with destructive operations like `rm -rf`. Never delete files outside of your working directory `/workspace` unless explicitly requested.
- **Network Access**: You can access the internet to download tools or perform web searches. Be cautious of downloading unknown or unverified binaries.
- **Malicious Commands**: If you identify a command as potentially malicious or dangerous (e.g. fork bombs, deleting system libraries), you MUST refuse to run it and warn the user.
