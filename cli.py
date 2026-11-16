from openai import APIError

from agent.agent import Agent, providers_from_env

HELP = "Commands: /new starts a new conversation, /quit exits."

def main() -> None:
    try:
        agent = Agent(providers_from_env(), verbose = True)
    except RuntimeError as error:
        print(error)
        return

    print("PitchPilot: describe your space and viewing distance, and I'll recommend an LED wall.")
    print(HELP)
    print()

    while True:
        try:
            user_text = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_text:
            continue
        if user_text.lower() in {"/quit", "quit", "exit"}:
            print("Bye!")
            break
        if user_text.lower() == "/new":
            agent.reset()
            print("Started a new conversation.\n")
            continue

        try:
            answer = agent.ask(user_text)
        except (APIError, RuntimeError) as error:
            print(f"\n[error] {error}\n")
            continue

        print(f"\nPitchPilot: {answer}\n")


if __name__ == "__main__":
    main()