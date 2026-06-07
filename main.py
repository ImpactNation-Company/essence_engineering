import sys
from core.orchestrator import Orchestrator

def main():
    if len(sys.argv) < 3:
        print('Usage: python main.py ask "your question"')
        return

    command = sys.argv[1]
    query = sys.argv[2]

    if command != "ask":
        print("Only 'ask' supported in v0")
        return

    system = Orchestrator()
    result = system.run(query)

    print("\n=== FINAL OUTPUT ===")
    print(result["response"])
    print("\n=== REASONING TRACE ===")
    print(result["reasoning"])

if __name__ == "__main__":
    main()