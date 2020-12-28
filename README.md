# Z.E. Schedule Shifter

The Renault Zoe BEV has the ability to control charging and air conditioning
using calendar-schedules, or via remote control. For unknown reasons,
remote-control (via the "My Renault" App or API) is only possible as long as
the car is set to "scheduled mode".

This, however, poses a problem: You need to have one active schedule for each
charging and air conditioning. However, you don’t want them to trigger when you
don’t need them, and you don’t want to remember shifting them around once per
week.

Here `Z.E. Schedule Shifter` comes into play: It will take control of one of
the 5 "Programs" of the cars calendar-schedules, and shift them by one day
forward every day. This allows you to leave both charging and air conditioning
on its "scheduled" modes, and forget about it, without them triggering
unsolicitedly.

## How to use
### Prerequisites
* Car is paired to renault data-services
* Car has data-exchange allowed and activated
* A login to "my renault" services (i.e., the app)
* Any computer able to run `docker` containers, with internet connectivity

### How to …
* Set your cars charging and air-conditioning modes to "scheduled" on the cars multi-media system.
* Run the container:
  * `docker` (no compose): Pull and start the container: `docker run -d --restart unless-stopped --name zescheduleshifter nebukadneza/zescheduleshifter:latest`
  * `docker-compose`: Find the `docker-compose.yaml` in this repository, and start it: `docker-compose up -d`
* Log into your account:
  * `docker` (no compose): `docker exec -it zescheduleshifter renault-api status`
  * `docker-compose`: `docker-compose exec zescheduleshifter renault-api status`
  * This will ask you for your region (such as `en_US` or `de_DE`), your user/password for myrenault and let you select your account and vehicle. Please answer `Y`es whan asked about saving to the credential-store. This store will contain tokens to access your account, but not your (plain) user or password. It is saved in a anonymous `docker volume`.
* The service should pick up your login after a short while. Check logs with:
  * `docker` (no compose): `docker logs -f zescheduleshifter`
  * `docker-compose`: `docker-compose logs -f`
  * … and wait for debug output to appear. Your `5`th schedules should now be shifted to tomorrow and tomorrow only, at 15:15 (UTC).

### Customizing
By default, the last schedules (No. `5`) are controlled. It is always made sure
that these are activated and only one entry is present in them — tomorrow at
15:15 (UTC). If you want the service to control another. If you want to change
this, use the environment variables `CHARGE_SCHEDULE_TO_CONTROL` and
`HVAC_SCHEDULE_TO_CONTROL` respectively, setting them to a number between `1`
and `5`. The `docker-compose` file has them already defined for you. For
`docker`, see the `-e` parameter of the `run` command.

# Thanks
Thanks to …
* `epenet` and `hacf-fr` for their great [`renault-api`](https://github.com/hacf-fr/renault-api)!
