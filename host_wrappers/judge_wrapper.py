from host_wrappers.base_wrapper import create_wrapper_app

app = create_wrapper_app("JUDGE_COMMAND", "judge generate")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9004)
