import { RuntimeApiRequestError } from "../../api/http";

type ApiErrorAlertProps = {
  error: unknown;
  title?: string;
};

export default function ApiErrorAlert({ error, title = "Request failed" }: ApiErrorAlertProps) {
  if (error instanceof RuntimeApiRequestError) {
    return (
      <div className="rounded-xl border border-danger/40 bg-danger/10 p-4 text-sm">
        <p className="font-semibold text-danger">{title}</p>
        <p className="mt-1 text-danger">{error.detail}</p>
        <p className="mt-2 font-mono text-xs text-danger/80">
          status={error.status} code={error.code}
          {error.requestId ? ` request_id=${error.requestId}` : ""}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
      <p className="font-semibold">{title}</p>
      <p className="mt-1">{String(error)}</p>
    </div>
  );
}
