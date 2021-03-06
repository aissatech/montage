import template from './round.html';

const Component = {
  bindings: {
    campaign: '=',
    last: '=',
    round: '=',
  },
  controller,
  template,
};

function controller(
  adminService,
  alertService) {
  const vm = this;

  vm.activateRound = activateRound;
  vm.finalizeRound = finalizeRound;
  vm.pauseRound = pauseRound;
  vm.populateRound = populateRound;
  vm.editRound = () => { vm.round.edit = true; };

  // functions

  vm.$onInit = () => {
    getRoundDetails(vm.round);
    getRoundResults(vm.round);
  };

  /**
   * 
   */
  function activateRound() {
    adminService
      .activateRound(vm.round.id)
      .then(() => {
        getRoundDetails(vm.round);
      })
      .catch(alertService.error);
  }

  /**
   * 
   */
  function finalizeRound() {
    vm.round.details.is_closeable = false;
    vm.campaign.rounds.push({ showForm: true });
  }

  /**
   * Getting details of round including jurors ratings
   * @param {Object} round
   */
  function getRoundDetails(round) {
    adminService
      .getRound(round.id)
      .then((data) => {
        angular.extend(round, data.data);
      })
      .catch(alertService.error);
  }

  /**
   * Getting current results of round
   * @param {Object} round
   */
  function getRoundResults(round) {
    adminService
      .previewRound(round.id)
      .then((data) => {
        angular.extend(round, {
          details: data.data,
        });
        if (!round.details.ratings) { return; }
        round.details.ratings = {
          labels: Object.keys(round.details.ratings)
            .map(label => `${(parseFloat(label) * 10).toFixed(2)}/10`),
          values: Object.keys(round.details.ratings)
            .map(key => round.details.ratings[key]),
        };
      })
      .catch(alertService.error);
  }

  /**
   * 
   */
  function pauseRound() {
    adminService
      .pauseRound(vm.round.id)
      .then(() => {
        getRoundDetails(vm.round);
      })
      .catch(alertService.error);
  }

  /**
   * 
   */
  function populateRound() {
    adminService
      .populateRound(vm.round.id, {
        import_method: 'gistcsv',
        gist_url: 'https://gist.githubusercontent.com/yarl/bc4b89847f9ced089f7169bbfec79841/raw/c8bd23d3b354ce9d20de578245e4dc7c9f095fb0/wlm2015_fr_5.csv',
      })
      .catch(alertService.error);
  }
}

export default Component;
