# React Starter Template
## Technologies
This template is a quick start into

## Architecture
```
src
│ __mocks__ (jest)
│ __tests__ (jest)
| App (root react component)
| assets (images and other assets)
  |_ public (assets that shouldn't be hash named)
| common (shared functions and objects)
| components (all react components that are not tied to a route)
| hooks (all react components that are not tied to a route)
| route (route config)
| screens (all react components that are tied to a route)
| scss (all scss style - container of local.scss and global.scss)
| index.ejs (root index html file)
| index.jsx (root index js file - loads App)
```

## Testing
There are 2 type of tests that are currently supported, being unit testing and integration testing.

### Unit Testing
[React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) is used to write and run unit tests.

* Run `npm test` to run the testing workflow.
* The test files are located in the `src/__tests__` folder and they follow they should follow the same folder structure as the components they are targeting.
* The test files should be in the format `<name>.test.{js|jsx}`
* [@testing-library/jest-dom](https://www.npmjs.com/package/@testing-library/jest-dom) is used to extend jest's matchers to simplify the checking of an elements attributtes in order to target a specific elemen during the testing process.

### Intergration Testing
[Cypress](https://www.cypress.io/) is the test automation tool that is used for integration tests and below is the workflow of getting started.

* Run `npm run cy:e2e` to run the test specs. Cypress runs on a separate `Electron powered` application and will open as its own application. The command starts a dev-server on port `8080` and then runs `cypress` command as defined in the `package.json`.

Note: running it for the first time might not open up immediately due to the completion of the setup process. Hence, if that occurs, the above command has to be re-run.

Also, ensure the port 8080 is not in use to run the tests.

* If you want to change the port address for running the tests, change the port in the `baseUrl` located in the file `cypress/cypress.json` to the port of your choice.

* To run a specific test, navigate to the window that Cypress has opened and click on the `spec file` of interest. Cypress will then open up a Browser instance that will then run the tests.

* In case you want to open all the tests files under cypress and manually run individual tests use the command `npm run cy:open`.

* Currently the integration tests are not part of our CI/CD workflow and hence should be run manually.
