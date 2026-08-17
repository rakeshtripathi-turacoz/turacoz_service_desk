"""Knowledge base search and article suggestion (PRD modules 10 and 18)."""

import re

import frappe
from frappe.utils import cint, now_datetime, strip_html

STOP_WORDS = {
	"the", "and", "for", "with", "not", "you", "your", "are", "was", "this", "that",
	"from", "have", "has", "but", "can", "cannot", "will", "would", "please", "issue",
	"problem", "error", "help", "need", "unable", "when", "what", "how", "why", "does",
	"there", "their", "been", "into", "about", "after", "before", "again", "also",
}


def tokenize(text, minimum=3):
	if not text:
		return []
	words = re.findall(r"[a-zA-Z0-9]+", strip_html(str(text)).lower())
	return [w for w in words if len(w) >= minimum and w not in STOP_WORDS]


@frappe.whitelist()
def suggest(subject=None, description=None, category=None, sub_category=None, limit=5):
	"""Rank published articles against a ticket's text and category."""
	limit = cint(limit) or 5
	tokens = set(tokenize(subject)) | set(tokenize(description))

	filters = {"status": "Published"}
	articles = frappe.get_all(
		"Knowledge Article",
		filters=filters,
		fields=["name", "title", "article_type", "category", "sub_category", "keywords",
		        "view_count", "helpful_count", "not_helpful_count"],
		limit_page_length=0,
	)
	if not articles:
		return []

	scored = []
	for article in articles:
		score = 0
		article_tokens = set(tokenize(article.title)) | set(
			tokenize((article.keywords or "").replace(",", " "))
		)
		overlap = tokens & article_tokens
		score += len(overlap) * 5
		if category and article.category == category:
			score += 4
		if sub_category and article.sub_category == sub_category:
			score += 3
		score += min(cint(article.helpful_count), 10)
		score -= min(cint(article.not_helpful_count), 5)
		if score <= 0:
			continue
		scored.append({
			"name": article.name,
			"title": article.title,
			"article_type": article.article_type,
			"category": article.category,
			"score": score,
			"matched": sorted(overlap)[:6],
		})

	scored.sort(key=lambda a: (-a["score"], a["title"]))
	return scored[:limit]


@frappe.whitelist()
def search(query=None, category=None, article_type=None, limit=20):
	"""Free text search across published articles."""
	filters = {"status": "Published"}
	if category:
		filters["category"] = category
	if article_type:
		filters["article_type"] = article_type

	or_filters = None
	if query:
		or_filters = [
			["title", "like", f"%{query}%"],
			["keywords", "like", f"%{query}%"],
			["content", "like", f"%{query}%"],
		]

	return frappe.get_all(
		"Knowledge Article",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "title", "article_type", "category", "view_count", "helpful_count",
		        "modified"],
		order_by="helpful_count desc, view_count desc, modified desc",
		limit=cint(limit) or 20,
	)


@frappe.whitelist()
def record_view(article):
	frappe.db.set_value("Knowledge Article", article, "view_count",
	                    cint(frappe.db.get_value("Knowledge Article", article, "view_count")) + 1,
	                    update_modified=False)
	return True


@frappe.whitelist()
def rate(article, helpful=1):
	field = "helpful_count" if cint(helpful) else "not_helpful_count"
	frappe.db.set_value("Knowledge Article", article, field,
	                    cint(frappe.db.get_value("Knowledge Article", article, field)) + 1,
	                    update_modified=False)
	return True


def create_from_ticket(ticket):
	"""Draft an article out of a resolved ticket so the fix is not lost."""
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("read")
	if not doc.resolution:
		frappe.throw(frappe._("This ticket has no resolution to publish."))

	article = frappe.get_doc({
		"doctype": "Knowledge Article",
		"title": doc.subject,
		"article_type": "Troubleshooting",
		"status": "Draft",
		"category": doc.category,
		"sub_category": doc.sub_category,
		"author": frappe.session.user,
		"content": (
			f"<h3>Problem</h3>{doc.description or doc.short_description or ''}"
			f"<h3>Root Cause</h3>{doc.root_cause or '-'}"
			f"<h3>Resolution</h3>{doc.resolution}"
		),
		"keywords": ", ".join(sorted(set(tokenize(doc.subject)))[:12]),
		"related_records": [{
			"reference_doctype": "Service Ticket",
			"reference_name": doc.name,
			"relationship": "Related",
		}],
	})
	article.insert(ignore_permissions=True)
	frappe.db.set_value("Service Ticket", doc.name, "knowledge_article", article.name,
	                    update_modified=False)
	return article.name


@frappe.whitelist()
def create_article_from_ticket(ticket):
	name = create_from_ticket(ticket)
	frappe.db.commit()
	return name


def approve_article(article):
	doc = frappe.get_doc("Knowledge Article", article)
	doc.status = "Published"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	doc.version = cint(doc.version) + 1
	doc.save()
	return doc.name
