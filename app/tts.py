import edge_tts


async def synthesize(text, voice, out_path) -> bool:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await edge_tts.Communicate(text, voice).save(str(out_path))
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        try:
            if out_path.exists():
                out_path.unlink()
        except OSError:
            pass
        return False
