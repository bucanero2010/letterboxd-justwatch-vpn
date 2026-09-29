import App from "@/components/App";
import data from "@/public/data.json";
import type { SiteData } from "@/lib/types";

export default function Home() {
  return <App data={data as SiteData} />;
}
