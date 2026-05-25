declare module 'vis-timeline/standalone' {
    export class Timeline {
        constructor(container: HTMLElement, items: any, options?: any);
        on(event: string, callback: (properties: any) => void): void;
        destroy(): void;
    }
}

declare module 'vis-data/standalone' {
    export class DataSet<T = any> {
        constructor(data?: T[], options?: any);
        add(data: T | T[]): void;
        update(data: T | T[]): void;
        remove(id: string | number | (string | number)[]): void;
    }
}
