// User type for authentication
export interface User {
    id: number | string;
    username: string;
    email?: string;
    createdAt?: Date | string;
}

export enum AuthMode {
    LOGIN = 'LOGIN',
    SIGNUP = 'SIGNUP'
}
