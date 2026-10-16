"""viva_genesis visualization classes.

Registered pbg ``Visualization`` subclasses, one concern per module. The
workbench resolves ``address: local:<ClassName>`` by importing this package's
submodules and registering every ``Visualization`` subclass by name (see
vivarium_workbench.env_worker). Keep viz classes HERE (not at the package root)
so both the dashboard resolver and the readiness linter discover them.
"""
