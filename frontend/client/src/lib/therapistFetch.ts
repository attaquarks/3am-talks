export async function therapistFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
    const response = await fetch(endpoint, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData?.detail?.message || errorData?.detail || errorData?.message || "Request failed";
        throw new Error(typeof message === "string" ? message : "Request failed");
    }

    return response;
}

export async function therapistFetchJson<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const res = await therapistFetch(endpoint, options);
    return (await res.json()) as T;
}
