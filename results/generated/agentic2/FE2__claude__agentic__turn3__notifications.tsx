'use client';

import * as React from 'react';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Checkbox from '@mui/material/Checkbox';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormGroup from '@mui/material/FormGroup';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { apiRequest } from '@/lib/api-request';

interface NotificationPreferences {
  emailProductUpdates: boolean;
  emailSecurityUpdates: boolean;
  phoneProductUpdates: boolean;
  phoneSecurityUpdates: boolean;
}

export function Notifications(): React.JSX.Element {
  const [preferences, setPreferences] = React.useState<NotificationPreferences>({
    emailProductUpdates: true,
    emailSecurityUpdates: false,
    phoneProductUpdates: true,
    phoneSecurityUpdates: false,
  });
  const [isSaving, setIsSaving] = React.useState(false);

  const handleChange = React.useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = event.target;
    setPreferences((prev) => ({ ...prev, [name]: checked }));
  }, []);

  const handleSubmit = React.useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setIsSaving(true);
      try {
        await apiRequest('/users/notification-preferences', {
          method: 'PUT',
          body: JSON.stringify(preferences),
        });
      } finally {
        setIsSaving(false);
      }
    },
    [preferences]
  );

  return (
    <form onSubmit={handleSubmit}>
      <Card>
        <CardHeader subheader="Manage the notifications" title="Notifications" />
        <Divider />
        <CardContent>
          <Grid container spacing={6} wrap="wrap">
            <Grid
              size={{
                md: 4,
                sm: 6,
                xs: 12,
              }}
            >
              <Stack spacing={1}>
                <Typography variant="h6">Email</Typography>
                <FormGroup>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.emailProductUpdates}
                        name="emailProductUpdates"
                        onChange={handleChange}
                      />
                    }
                    label="Product updates"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.emailSecurityUpdates}
                        name="emailSecurityUpdates"
                        onChange={handleChange}
                      />
                    }
                    label="Security updates"
                  />
                </FormGroup>
              </Stack>
            </Grid>
            <Grid
              size={{
                md: 4,
                sm: 6,
                xs: 12,
              }}
            >
              <Stack spacing={1}>
                <Typography variant="h6">Phone</Typography>
                <FormGroup>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.phoneProductUpdates}
                        name="phoneProductUpdates"
                        onChange={handleChange}
                      />
                    }
                    label="Email"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={preferences.phoneSecurityUpdates}
                        name="phoneSecurityUpdates"
                        onChange={handleChange}
                      />
                    }
                    label="Security updates"
                  />
                </FormGroup>
              </Stack>
            </Grid>
          </Grid>
        </CardContent>
        <Divider />
        <CardActions sx={{ justifyContent: 'flex-end' }}>
          <Button disabled={isSaving} type="submit" variant="contained">
            Save changes
          </Button>
        </CardActions>
      </Card>
    </form>
  );
}
