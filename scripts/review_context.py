"""Refresh only allowlisted source context; semantic revisions survive irrelevant HTML changes."""
from scripts.scan_sources import Fetcher, VERSION, digest, normalized, html_document, pdf_document, ScanError


def refresh_context(bundle, config, fetcher=None):
    fetcher=fetcher or Fetcher(config)
    profiles={s["id"]:s for s in config["sources"] if s.get("enabled",True)}
    contexts, statuses, documents={}, {}, {}
    for cand in bundle["candidates"]:
        meta=cand["source_metadata"];url=meta["url"]
        source=profiles.get(meta["source_id"])
        key=(meta["source_id"],url,meta["revision_id"])
        if key in statuses:continue
        try:
            if not source:raise ScanError("source_disabled_or_unregistered")
            is_attachment=url!=source["url"]
            is_pdf=is_attachment or source.get("format")=="pdf"
            if is_attachment:
                if meta.get("parent_url")!=source["url"] or url not in source.get("known_attachment_urls",[]):
                    raise ScanError("source_profile_mismatch")
                if source["url"] not in documents:
                    parent=fetcher.get(source["url"],{},2*1024*1024)
                    if parent["status"]!=200 or "text/html" not in parent["headers"].get("content-type","").lower():
                        raise ScanError("attachment_parent_unavailable")
                    documents[source["url"]]=html_document(parent["body"],source,parent["url"],config["allowed_hosts"])
                if url not in {a["url"] for a in documents[source["url"]][1]}:raise ScanError("attachment_not_discovered")
            if url not in documents:
                response=fetcher.get(url,{},10*1024*1024 if is_pdf else 2*1024*1024)
                if response["status"]!=200:raise ScanError("http_"+str(response["status"]))
                if is_pdf:
                    if not response["body"].startswith(b"%PDF-"):raise ScanError("unexpected_content_type")
                    documents[url]=(pdf_document(response["body"]),[])
                else:
                    if "text/html" not in response["headers"].get("content-type","").lower():raise ScanError("unexpected_content_type")
                    documents[url]=html_document(response["body"],source,response["url"],config["allowed_hosts"])
            blocks,attachments=documents[url]
            semantic=digest([[normalized(b["text"]) for b in blocks],attachments])
            revision=digest([url,semantic,digest([VERSION,source])])
            if revision!=meta["revision_id"]:raise ScanError("source_revision_changed_requires_rescan")
            contexts[url]=blocks
            statuses[key]="fresh_semantic_revision_matched"
        except Exception as error:
            statuses[key]=str(error) if isinstance(error,ScanError) else type(error).__name__
    # Multiple revisions of the same URL cannot share a supposedly fresh context.
    for cand in bundle["candidates"]:
        meta=cand["source_metadata"]
        if statuses.get((meta["source_id"],meta["url"],meta["revision_id"]))!="fresh_semantic_revision_matched":contexts.pop(meta["url"],None)
    return contexts,{c["candidate_id"]:statuses[(c["source_metadata"]["source_id"],c["source_metadata"]["url"],c["source_metadata"]["revision_id"])] for c in bundle["candidates"]},fetcher.count
