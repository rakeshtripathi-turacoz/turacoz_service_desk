"""Consistent JSON envelope for every service desk REST endpoint (PRD section 8)."""

import functools

import frappe


def ok(data=None, message=None, **extra):
	payload = {"success": True, "data": data}
	if message:
		payload["message"] = message
	payload.update(extra)
	return payload


def error(message, code="error", status=417):
	frappe.local.response["http_status_code"] = status
	return {"success": False, "error": {"code": code, "message": message}}


def api(fn):
	"""Wrap an endpoint so business errors come back as JSON instead of a traceback."""

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except frappe.PermissionError as exc:
			frappe.db.rollback()
			return error(str(exc) or "Not permitted", "permission_denied", 403)
		except frappe.DoesNotExistError as exc:
			frappe.db.rollback()
			return error(str(exc) or "Not found", "not_found", 404)
		except frappe.ValidationError as exc:
			frappe.db.rollback()
			return error(frappe.utils.strip_html(str(exc)), "validation_error", 417)
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), f"Service desk API failed: {fn.__name__}")
			return error("Unexpected server error", "server_error", 500)

	return wrapper
