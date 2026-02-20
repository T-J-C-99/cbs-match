export default function NotFoundPage() {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col items-center justify-center px-6 text-center">
      <h1 className="text-3xl font-semibold text-slate-900">Page not found</h1>
      <p className="mt-3 text-slate-600">The page you requested doesn’t exist.</p>
      <a href="/landing" className="mt-6 rounded bg-black px-4 py-2 text-sm font-medium text-white">
        Back to landing
      </a>
    </div>
  );
}
