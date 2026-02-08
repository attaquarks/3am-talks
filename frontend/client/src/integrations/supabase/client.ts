// This is a mock Supabase client that redirects calls to the local Express API.
// It allows us to keep using the existing Supabase-dependent code while the project is paused.

export const supabaseUrl = 'http://localhost:5050';
export const supabaseAnonKey = 'mock-key';

const fetchApi = async (endpoint: string, options: RequestInit = {}) => {
    const response = await fetch(endpoint, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ message: 'API request failed' }));
        throw error;
    }
    return response.json();
};

export const supabase = {
    auth: {
        getSession: async () => {
            try {
                const user = await fetchApi('/api/user');
                return { data: { session: { user, access_token: 'mock-token' } }, error: null };
            } catch (e) {
                return { data: { session: null }, error: e };
            }
        },
        getUser: async () => {
            try {
                const user = await fetchApi('/api/user');
                return { data: { user }, error: null };
            } catch (e) {
                return { data: { user: null }, error: e };
            }
        },
        updateUser: async (attributes: any) => {
            try {
                return { data: { user: attributes }, error: null };
            } catch (e: any) {
                return { data: { user: null }, error: { message: e.message || 'Update failed' } };
            }
        },
        signInWithPassword: async ({ email, password }: any) => {
            try {
                const user = await fetchApi('/api/login', {
                    method: 'POST',
                    body: JSON.stringify({ email, password }),
                });
                return { data: { user }, error: null };
            } catch (e) {
                return { data: { user: null }, error: e };
            }
        },
        signUp: async ({ email, password, options }: any) => {
            try {
                const user = await fetchApi('/api/register', {
                    method: 'POST',
                    body: JSON.stringify({ email, password, name: options?.data?.name || 'User' }),
                });
                return { data: { user }, error: null };
            } catch (e) {
                return { data: { user: null }, error: e };
            }
        },
        signInWithOAuth: async ({ provider }: any) => {
            try {
                const user = await fetchApi('/api/auth/social', {
                    method: 'POST',
                    body: JSON.stringify({
                        email: `mock-${provider}@example.com`,
                        name: `Mock ${provider} User`,
                        provider
                    }),
                });
                return { data: { user }, error: null };
            } catch (e) {
                return { data: { user: null }, error: e };
            }
        },
        signOut: async () => {
            try {
                await fetchApi('/api/logout', { method: 'POST' });
                return { error: null };
            } catch (e) {
                return { error: e };
            }
        },
        onAuthStateChange: (callback: any) => {
            return { data: { subscription: { unsubscribe: () => { } } } };
        },
    },
    from: (table: string) => {
        const createQueryHandler = (method: string, body?: any, filters: any = {}) => {
            const handler: any = {
                eq: (column: string, value: any) => {
                    filters[column] = value;
                    return handler;
                },
                order: (column: string, options?: any) => {
                    return handler;
                },
                single: async () => {
                    try {
                        const filterVal = Object.values(filters)[0];
                        const url = filterVal ? `/api/data/${table}/${filterVal}` : `/api/data/${table}`;
                        const data = await fetchApi(url, {
                            method,
                            body: body ? JSON.stringify(body) : undefined,
                        });
                        return { data, error: null };
                    } catch (e: any) {
                        return { data: null, error: { message: e.message || 'Request failed' } };
                    }
                },
                select: () => handler,
                insert: (values: any) => {
                    body = values[0];
                    return handler;
                },
                then: (resolve: any) => {
                    const filterVal = Object.values(filters)[0];
                    const url = filterVal ? `/api/data/${table}/${filterVal}` : `/api/data/${table}`;
                    fetchApi(url, {
                        method,
                        body: body ? JSON.stringify(body) : undefined,
                    }).then(data => resolve({ data, error: null })).catch(e => resolve({ data: null, error: e }));
                }
            };
            return handler;
        };

        return {
            select: (columns?: string) => createQueryHandler('GET'),
            update: (values: any) => createQueryHandler('PATCH', values),
            insert: (values: any) => createQueryHandler('POST', values[0]),
            upsert: (values: any) => createQueryHandler('POST', values[0]),
            delete: () => createQueryHandler('DELETE'),
        };
    },
    functions: {
        invoke: async (name: string, options?: any) => {
            try {
                if (name === 'ai-chat') {
                    const body = options?.body || {};
                    const data = await fetchApi('/api/chat', {
                        method: 'POST',
                        body: JSON.stringify({
                            message: body.message || '',
                            conversation_id: body.conversation_id || null,
                            conversation_history: body.conversation_history || [],
                        }),
                    });
                    return { data, error: null };
                }
                return { data: {}, error: null };
            } catch (e: any) {
                return { data: null, error: { message: e.message || 'Function failed' } };
            }
        }
    },
    channel: (name: string) => ({
        on: (event: string, config: any, callback: (payload: any) => void) => ({
            subscribe: () => ({
                unsubscribe: () => { }
            })
        })
    })
};