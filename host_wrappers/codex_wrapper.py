from host_wrappers.base_wrapper import create_wrapper_app

app = create_wrapper_app("CODEX_COMMAND", "codex exec --skip-git-repo-check")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9001)
