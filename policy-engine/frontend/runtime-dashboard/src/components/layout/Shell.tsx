import type { PropsWithChildren } from "react";

import Header from "./Header";
import Sidebar from "./Sidebar";

export default function Shell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen md:flex">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <Header />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
