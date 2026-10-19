import { isRouteErrorResponse, Link, useRouteError } from "react-router";
import { Button } from "@/components/ui/button";

export const RouteErrorPage = () => {
  const error = useRouteError();

  const isHttpError = isRouteErrorResponse(error);
  const statusCode = isHttpError ? error.status : 500;
  const statusText = isHttpError
    ? error.statusText
    : error instanceof Error
      ? error.message
      : "Something went wrong";

  const description = getErrorDescription(statusCode, isHttpError);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -top-1/4 left-1/2 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-destructive/4 blur-3xl" />
        <div className="absolute -bottom-1/4 right-0 h-[400px] w-[400px] rounded-full bg-muted/40 blur-3xl" />
      </div>

      <div className="relative z-10 flex max-w-lg flex-col items-start gap-6">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center rounded-full border border-destructive/20 bg-destructive/10 px-2.5 py-0.5 text-xs font-medium tracking-wide text-destructive">
            Error {statusCode}
          </span>
          <span className="h-px w-8 bg-border" />
          <span className="text-xs text-muted-foreground">{statusText}</span>
        </div>

        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">
            {getErrorTitle(statusCode)}
          </h1>
          <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        </div>

        {/* Error details — only shown in development */}
        {import.meta.env.DEV &&
          !isHttpError &&
          error instanceof Error &&
          error.stack && (
            <details className="w-full">
              <summary className="cursor-pointer text-xs text-muted-foreground transition-colors hover:text-foreground">
                Show error details
              </summary>
              <pre className="mt-2 max-h-40 overflow-auto rounded-lg border border-border bg-muted/50 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
                {error.stack}
              </pre>
            </details>
          )}

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button nativeButton={false} render={<Link to="/" />}>
            Back to overview
          </Button>
          <Button
            className="cursor-pointer"
            variant="outline"
            onClick={() => window.location.reload()}
          >
            Reload page
          </Button>
        </div>
      </div>
    </div>
  );
};

function getErrorTitle(statusCode: number): string {
  switch (statusCode) {
    case 400:
      return "Bad request";
    case 401:
      return "Not authorized";
    case 403:
      return "Access denied";
    case 404:
      return "Page not found";
    case 408:
      return "Request timed out";
    case 429:
      return "Too many requests";
    case 500:
      return "Something went wrong";
    case 502:
      return "Bad gateway";
    case 503:
      return "Service unavailable";
    default:
      return "An error occurred";
  }
}

function getErrorDescription(statusCode: number, isHttpError: boolean): string {
  if (!isHttpError) {
    return "An unexpected error occurred while loading this page. You can try reloading, or head back to the overview.";
  }

  switch (statusCode) {
    case 400:
      return "The request couldn't be processed. Please check the URL and try again.";
    case 401:
      return "You need to sign in to access this page. Please sign in and try again.";
    case 403:
      return "You don't have permission to view this page. Contact your organization admin if you believe this is a mistake.";
    case 404:
      return "The page you're looking for doesn't exist or may have been moved.";
    case 408:
      return "The request took too long to complete. Please check your connection and try again.";
    case 429:
      return "You've made too many requests. Please wait a moment before trying again.";
    case 500:
      return "Something went wrong on our end. We're working on it — please try again in a moment.";
    case 502:
      return "We received an invalid response from the server. Please try again shortly.";
    case 503:
      return "The service is temporarily unavailable. Please try again in a few minutes.";
    default:
      return "Something unexpected happened. You can try reloading the page, or head back to the overview.";
  }
}
