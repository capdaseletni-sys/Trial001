async def get_api_events():
    """Checks mirrors and returns events with a wider time window for debugging."""
    now = datetime.now(timezone.utc)
    # Widen window to 12 hours to ensure we catch upcoming matches
    start_window = now - timedelta(hours=2)
    end_window = now + timedelta(hours=10)
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for mirror in MIRRORS:
            try:
                log.info(f"Checking mirror: {mirror}")
                r = await client.get(mirror, timeout=10)
                if r.status_code == 200:
                    api_data = r.json()
                    events = []
                    
                    # Log all found categories for debugging
                    categories = [g.get("category") for g in api_data.get("streams", [])]
                    log.info(f"Categories found: {categories}")

                    for group in api_data.get("streams", []):
                        sport = group.get("category")
                        if sport == "24/7 Streams": continue
                        
                        for ev in group.get("streams", []):
                            ts = ev.get("starts_at")
                            if not ts: continue
                            
                            event_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                            
                            # Log the first few events found to see their start times
                            if len(events) < 3:
                                log.info(f"Checking: {ev.get('name')} | Starts: {event_dt}")

                            if start_window <= event_dt <= end_window:
                                events.append({
                                    "sport": sport,
                                    "event": ev.get("name"),
                                    "link": ev.get("iframe"),
                                    "logo": ev.get("poster"),
                                    "timestamp": ts
                                })
                                
                    if events:
                        log.info(f"Found {len(events)} valid events on {mirror}")
                        return events
                    else:
                        log.warning(f"No events matched the time window on {mirror}")
            except Exception as e:
                log.warning(f"Mirror {mirror} failed: {e}")
    return []
