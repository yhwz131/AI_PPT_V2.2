/**
 * E2E Smoke Test: PPTTalK Frontend <-> Backend integration
 *
 * This script validates the complete flow:
 *   1. Upload PPT → conversion task created
 *   2. Poll conversion status → PDF ready
 *   3. Generate voice-over script
 *   4. Create digital human generation task
 *   5. Subscribe to SSE stream → receive events
 *
 * Run with: npx tsx test/e2e-smoke.ts
 *
 * Prerequisites: backend running on http://127.0.0.1:9088
 */
declare const API: string;
interface ApiRes<T = any> {
    code: number;
    message: string;
    data: T;
}
declare function apiGet<T>(path: string): Promise<ApiRes<T>>;
declare function apiPost<T>(path: string, body?: any): Promise<ApiRes<T>>;
declare function log(step: string, msg: string): void;
declare function sleep(ms: number): Promise<unknown>;
declare function testHealthcheck(): Promise<void>;
declare function testConversionEndpoint(): Promise<void>;
declare function testTaskStatusEndpoint(): Promise<void>;
declare function testDigitalHumanCatalog(): Promise<void>;
declare function testVideoCatalog(): Promise<void>;
declare function testSSEEndpoint(): Promise<void>;
declare function testCreateTaskValidation(): Promise<void>;
declare function main(): Promise<void>;
