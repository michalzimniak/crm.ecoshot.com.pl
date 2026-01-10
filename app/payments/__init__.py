"""Payments module.

Keep this module side-effect free: the app factory imports models early (before
other blueprints/models), and importing routes/schemas here can trigger mapper
configuration too early.
"""
