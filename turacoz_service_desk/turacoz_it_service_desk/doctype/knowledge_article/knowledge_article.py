# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine.knowledge import tokenize


class KnowledgeArticle(Document):
	def validate(self):
		before = self.get_doc_before_save()
		self.author = self.author or frappe.session.user
		self.set_keywords()
		self.handle_publishing(before)

	def set_keywords(self):
		if self.keywords:
			return
		words = sorted(set(tokenize(self.title)) | set(tokenize(self.content)))
		self.keywords = ", ".join(words[:15])

	def handle_publishing(self, before):
		if self.status != "Published":
			return
		if not self.content:
			frappe.throw(_("An article needs content before it can be published."))
		if before and before.status != "Published":
			self.approved_by = frappe.session.user
			self.approved_on = now_datetime()
			self.version = cint(self.version) + 1
		elif before and (before.content != self.content or before.title != self.title):
			self.version = cint(self.version) + 1
