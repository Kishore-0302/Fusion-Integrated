import {
  Alert, Badge, Button, Card, Container, Grid, Group, Progress, Select, SimpleGrid,
  Stack, Table, Text,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import { FaChartBar, FaDownload, FaInfoCircle } from "react-icons/fa";

import { useAuth } from "../../../auth/AuthProvider";
import { errorMessage } from "../../../lib/http";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useCsvExport, useOutstandingLetters, useStats, type ExportKind,
} from "../api/hooks";

/** Staff only, matching the server. Hiding it is UX; the endpoint enforces. */
function ExportActions() {
  const exportCsv = useCsvExport();
  const running = exportCsv.isPending ? exportCsv.variables : undefined;

  function download(kind: ExportKind, label: string) {
    exportCsv.mutate(kind, {
      onError: (e) => notifications.show({
        color: "red", title: `${label} export failed`, message: errorMessage(e),
      }),
    });
  }

  return (
    <Group gap="xs">
      <Button
        variant="default" size="xs" leftSection={<FaDownload size={11} />}
        loading={running === "applications"}
        disabled={exportCsv.isPending && running !== "applications"}
        onClick={() => download("applications", "Applications")}
      >
        Applications CSV
      </Button>
      <Button
        variant="default" size="xs" leftSection={<FaDownload size={11} />}
        loading={running === "placements"}
        disabled={exportCsv.isPending && running !== "placements"}
        onClick={() => download("placements", "Placements")}
      >
        Placements CSV
      </Button>
    </Group>
  );
}

/** Rule 24's worklist. The office chases these before convocation, so it is a
 *  report rather than a screen of its own. */
function OutstandingLetters() {
  const { data, isPending, error } = useOutstandingLetters();
  const rows = data?.results ?? [];

  return (
    <Card padding="lg" mt="md">
      <Group justify="space-between" mb="xs">
        <div>
          <Text fw={600}>Offer letters outstanding</Text>
          <Text size="xs" c="dimmed">
            Rule 24 holds each of these students&apos; no-dues certificate.
          </Text>
        </div>
        {!error && (
          <Badge variant="light" color={rows.length ? "orange" : "green"}>
            {rows.length}
          </Badge>
        )}
      </Group>

      {isPending && <Text size="sm" c="dimmed">Loading…</Text>}
      {/* An unread list is not an empty one: "all filed" would be a false all-clear. */}
      {error && (
        <Text size="sm" c="red">
          This list could not be loaded, so it is not known whether any letter
          is outstanding. {errorMessage(error)}
        </Text>
      )}
      {!isPending && !error && !rows.length && (
        <Text size="sm" c="dimmed">Every placed student has filed one.</Text>
      )}

      {rows.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Company</Table.Th>
              <Table.Th>Source</Table.Th>
              <Table.Th>Not joining</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((r) => (
              <Table.Tr key={r.id}>
                <Table.Td>{r.company?.name ?? "—"}</Table.Td>
                <Table.Td>
                  {r.source === "off_campus" ? "Off campus" : "Campus"}
                </Table.Td>
                <Table.Td>
                  {r.not_joining_declared_at
                    ? (r.not_joining_was_late ? "Declared (late)" : "Declared")
                    : "—"}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

function Metric({ label, value, hint }: {
  label: string; value: string | number | null | undefined; hint?: string;
}) {
  return (
    <Card padding="md" withBorder>
      <Text size="xs" c="dimmed" tt="uppercase">{label}</Text>
      <Text fw={700} size="xl" mt={2}>{value ?? "—"}</Text>
      {hint && <Text size="xs" c="dimmed" mt={2}>{hint}</Text>}
    </Card>
  );
}

export default function ReportsPage() {
  const [season, setSeason] = useState("2026-27");
  const { data, isPending, error } = useStats(season);
  const { can } = useAuth();
  const isStaff = can("placement_cell.report.view");

  if (error) return <Container size="lg"><ErrorState error={error} /></Container>;
  if (isPending) return <Container size="lg"><Text c="dimmed">Loading…</Text></Container>;

  // An aggregate over a handful of people is not anonymous; the server suppresses it.
  if (data && data.available === false) {
    return (
      <Container size="lg">
        <PageHeader title="Placement Statistics" subtitle={data.season} />
        <Select
          label="Placement Season"
          value={season}
          onChange={(val) => val && setSeason(val)}
          data={["2024-25", "2025-26", "2026-27"]}
          mb="md"
        />
        <Alert variant="light" color="blue" icon={<FaInfoCircle />}
          title="Statistics are not published yet">
          <Text size="sm">
            {data.reason
              ?? "There is not enough data to publish figures for this season."}
          </Text>
        </Alert>
      </Container>
    );
  }

  return (
    <Container size="lg">
      <PageHeader
        title={isStaff ? "Placement Reports" : "Placement Statistics"}
        subtitle={isStaff
          ? `Operational figures for ${data?.season ?? season}`
          : `Anonymised figures for ${data?.season ?? season}`}
        action={isStaff ? <ExportActions /> : undefined}
      />

      <Select
        label="Placement Season"
        value={season}
        onChange={(val) => val && setSeason(val)}
        data={["2024-25", "2025-26", "2026-27"]}
        mb="md"
      />

      <SimpleGrid cols={{ base: 2, sm: 4 }} mb="md">
        <Metric label="Registered" value={data?.registered} />
        <Metric label="Placed" value={data?.placed} />
        <Metric
          label="Median CTC"
          value={data?.median_ctc ? `${data.median_ctc} LPA` : null}
        />
        <Metric
          label="Highest CTC"
          value={data?.max_ctc ? `${data.max_ctc} LPA` : null}
        />
      </SimpleGrid>

      {typeof data?.placement_rate === "number" && (
        <Card padding="lg" mb="md">
          <Group justify="space-between" mb={6}>
            <Text fw={600}>Placement rate</Text>
            <Text fw={700}>{data.placement_rate}%</Text>
          </Group>
          <Progress value={data.placement_rate} size="lg" color="teal" />
        </Card>
      )}

      <Grid>
        <Grid.Col span={{ base: 12, md: isStaff ? 7 : 12 }}>
          <Card padding="lg">
            <Group gap="xs" mb="sm">
              <FaChartBar size={13} />
              <Text fw={600}>By company</Text>
            </Group>
            {/* Small cells are suppressed server-side: a per-company count of
                one or two identifies the individual. */}
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Company</Table.Th>
                  <Table.Th ta="right">Placed</Table.Th>
                  {isStaff && <Table.Th ta="right">Highest CTC</Table.Th>}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(isStaff
                  ? (data?.by_company ?? []).map((c) => ({
                      name: c.company__name, placed: c.placed, top: c.top }))
                  : (data?.companies ?? []).map((c) => ({
                      name: c.company, placed: c.placed, top: null }))
                ).map((c) => (
                  <Table.Tr key={c.name}>
                    <Table.Td>{c.name}</Table.Td>
                    <Table.Td ta="right">{c.placed}</Table.Td>
                    {isStaff && <Table.Td ta="right">{c.top ?? "—"}</Table.Td>}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {!isStaff && (
              <Text size="xs" c="dimmed" mt="sm">
                Companies with very few placements are not listed, so that no
                individual can be identified from these figures.
              </Text>
            )}
          </Card>
        </Grid.Col>

        {isStaff && (
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Card padding="lg">
              <Text fw={600} mb="sm">Applications by status</Text>
              <Stack gap={6}>
                {Object.entries(data?.applications_by_status ?? {}).map(
                  ([status, n]) => (
                    <Group key={status} justify="space-between">
                      <Text size="sm">{status.replace(/_/g, " ")}</Text>
                      <Text size="sm" fw={600}>{n}</Text>
                    </Group>
                  ))}
              </Stack>
              <Group justify="space-between" mt="md">
                <Text size="sm" c="dimmed">Debarred</Text>
                <Text size="sm" fw={600}>{data?.debarred ?? 0}</Text>
              </Group>
            </Card>
          </Grid.Col>
        )}
      </Grid>

      {isStaff && <OutstandingLetters />}
    </Container>
  );
}
