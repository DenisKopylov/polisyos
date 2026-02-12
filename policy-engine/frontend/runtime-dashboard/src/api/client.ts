import createClient from "openapi-fetch";

import { API_BASE_URL } from "../lib/constants";
import type { paths } from "./types";

export const runtimeApiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
});
