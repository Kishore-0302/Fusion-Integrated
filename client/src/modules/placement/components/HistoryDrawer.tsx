import { Alert, Badge, Drawer, Group, Stack, Text, Timeline } from "@mantine/core";
import { FaInfoCircle } from "react-icons/fa";

import { ErrorState } from "../../../ui/components/ErrorState";
import { useApplicationHistory } from "../api/hooks";

const LANE_COLOUR: Record<string, string> = {
  staff: "blue", recruiter: "grape", student: "teal", system: "gray",
};

/** Every state change an application has been through (PC-AFR-009).
 *
 *  The server decides what this reader may see, so there is nothing to hide
 *  here — `redacted` only tells the user that reasons were withheld, rather
 *  than letting them think the trail is thin. */
export function HistoryDrawer({ applicationId, onClose }: {
  applicationId: number | null;
  onClose: () => void;
}) {
  const { data, isPending, error } = useApplicationHistory(
    applicationId ?? undefined);

  return (
    <Drawer
      opened={applicationId != null} onClose={onClose} position="right"
      size="md" title={<Text fw={700}>Application history</Text>}
    >
      {error && <ErrorState error={error} />}
      {isPending && !error && <Text size="sm" c="dimmed">Loading…</Text>}

      {data && (
        <Stack gap="md">
          {data.redacted && (
            <Alert variant="light" color="gray" icon={<FaInfoCircle />} p="sm">
              <Text size="xs">
                Internal review notes and the names of the people who acted are
                not shown here.
              </Text>
            </Alert>
          )}

          {!data.results.length && (
            <Text size="sm" c="dimmed">Nothing recorded yet.</Text>
          )}

          <Timeline active={data.results.length} bulletSize={16} lineWidth={2}>
            {data.results.map((entry, i) => (
              <Timeline.Item
                key={`${entry.at}-${i}`}
                color={LANE_COLOUR[entry.actor_label] ?? "gray"}
                title={
                  <Group gap="xs" wrap="nowrap">
                    <Text size="sm" fw={600}>
                      {entry.to_status.replace(/_/g, " ")}
                    </Text>
                    {entry.actor_label && (
                      <Badge size="xs" variant="light"
                        color={LANE_COLOUR[entry.actor_label] ?? "gray"}>
                        {entry.actor_label}
                      </Badge>
                    )}
                  </Group>
                }
              >
                <Text size="xs" c="dimmed">
                  from {entry.from_status.replace(/_/g, " ")} ·{" "}
                  {new Date(entry.at).toLocaleString()}
                </Text>
                {entry.reason && (
                  <Text size="sm" mt={4}>{entry.reason}</Text>
                )}
                {entry.actor_user_id != null && (
                  <Text size="xs" c="dimmed" mt={2}>
                    by user {entry.actor_user_id}
                  </Text>
                )}
              </Timeline.Item>
            ))}
          </Timeline>
        </Stack>
      )}
    </Drawer>
  );
}
