import neko_no_lib


def main():
    x = 15
    neko_no_lib.hello_people(x)
    for value in range(10):
        print(neko_no_lib.triple(value))


if __name__ == "__main__":
    main()
