'use client';

import * as React from 'react';
import Grid from '@mui/material/Unstable_Grid2';
import { Box, CircularProgress, Typography } from '@mui/material';

import { apiRequest } from '@/lib/api-client';
import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';

interface DashboardSummary {
  budget?: string | number;
  totalCustomers?: string | number;
  tasksProgress?: number;
  totalProfit?: string | number;
  salesData?: unknown;
  trafficData?: unknown;
  recentProducts?: unknown[];
  recentTransactions?: unknown[];
}

export default function DashboardPage(): React.JSX.Element {
  const [summary, setSummary] = React.useState<DashboardSummary | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    async function fetchSummary() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiRequest('/dashboard/summary');
        if (!cancelled) {
          setSummary(data ?? {});
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err?.message ?? 'Failed to load dashboard data.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchSummary();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="body2" color="text.secondary">
          Loading dashboard…
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          flexDirection: 'column',
          gap: 1,
        }}
      >
        <Typography variant="h6" color="error">
          Unable to load dashboard
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {error}
        </Typography>
      </Box>
    );
  }

  const {
    budget,
    totalCustomers,
    tasksProgress,
    totalProfit,
    salesData,
    trafficData,
    recentProducts = [],
    recentTransactions = [],
  } = summary ?? {};

  const safeRecentProducts = Array.isArray(recentProducts) ? recentProducts : [];
  const safeRecentTransactions = Array.isArray(recentTransactions) ? recentTransactions : [];

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 } }}>
      <Grid container spacing={3}>
        {/* KPI Cards */}
        <Grid xs={12} sm={6} lg={3}>
          <Budget value={budget} />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalCustomers value={totalCustomers} />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TasksProgress value={tasksProgress} />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalProfit value={totalProfit} />
        </Grid>

        {/* Charts */}
        <Grid xs={12} lg={8}>
          <Sales data={salesData} />
        </Grid>

        <Grid xs={12} lg={4}>
          <Traffic data={trafficData} />
        </Grid>

        {/* Tables */}
        <Grid xs={12} md={6}>
          <LatestProducts products={safeRecentProducts} />
        </Grid>

        <Grid xs={12} md={6}>
          <LatestOrders orders={safeRecentTransactions} />
        </Grid>
      </Grid>
    </Box>
  );
}
