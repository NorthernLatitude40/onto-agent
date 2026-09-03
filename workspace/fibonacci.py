
def fibonacci(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    else:
        list_fib = [0, 1]
        while len(list_fib) < n:
            next_fib = list_fib[-1] + list_fib[-2]
            list_fib.append(next_fib)
        return list_fib

if __name__ == "__main__":
    n = 10  # Calculate the first 10 Fibonacci numbers
    result = fibonacci(n)
    print(f"Fibonacci sequence up to {n} terms: {result}")
