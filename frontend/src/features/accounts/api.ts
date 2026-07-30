import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";

export interface UserRef {
  id: string;
  username: string;
  roles: string[];
}

interface Paginated<T> {
  results: T[];
}

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get<Paginated<UserRef>>("/users")).data.results,
  });
}
